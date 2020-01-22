import os
import sys
import ROOT
from math import *

from RDFtree import *

from utils import *

# typedefs
pair_f  = ROOT.pair('float','float')
pair_s  = ROOT.pair('string','string')
pair_ui = ROOT.std.pair('unsigned int','unsigned int')
vec_s   = ROOT.vector('string')
vec_f   = ROOT.vector('float')

"""
Class that configures RDFtree. Add new modules as class functions.
"""
class ConfigRDF():    

    def __init__(self, inputFiles, outputDir, outputFile, verbose):
        self.inputFiles = inputFiles
        self.p = RDFtree(outputDir=outputDir, inputFile=inputFiles[0], outputFile=outputFile)
        self.verbose = verbose
        self.recompute_vars = True
        self.use_externalSF_Iso = False
        self.use_externalSF_ID = False
        self.use_externalSF_Trigger = False
        self.def_modules = []        
        self.categories = {}
        self.iteration = -1
        # cut string that defines the category from its top category
        self.cut = ''
        # cut string that defines the category from 'defs'
        self.cut_base  = ''
        # unique category name
        self.category  = ''
        # name of the category defining the weight
        self.category_weight_base  = ''
        # name of the top category
        self.category_cut_base  = ''
        # full event weight of the category
        self.weight    = ''
        self.isMC  = True 
        self.lumi = 35.9
        self.xsec = 61526.7
        self.dataYear = '2016'        

    def set_sample_specifics(self,isMC,lumi,xsec,dataYear,era_ratios):
        self.isMC = isMC
        self.lumi = lumi
        self.xsec = xsec
        self.dataYear = dataYear
        self.era_ratios = pair_f(era_ratios[0],era_ratios[1])
        return
    
    """
    Branch defs
    """
    def _branch_defs(self):
        if self.iteration==0 and not hasattr(self, 'branch_defs_iter0'):
            Idx_mu2 = "Idx_mu2" if hasattr(self,'run_DIMUON') else ""
            self.def_modules.append( ROOT.getVars("Idx_mu1", Idx_mu2, self.isMC) )
            if self.recompute_vars:
                self.def_modules.append( ROOT.getCompVars("Idx_mu1", Idx_mu2, vec_s(), vec_s()) )          
            if self.isMC: 
                self.def_modules.append( ROOT.getLumiWeight(self.inputFiles, self.lumi, self.xsec) )
                # Merge BCDEF and GH into one overall SF
                if self.dataYear=='2016':
                    mus = ['1']
                    if hasattr(self,'run_DIMUON'): mus.append('2')
                    for mu in mus:
                        for syst in ['ISO', 'ID', 'Trigger']:
                            col1 = 'SelMuon'+mu+'_'+syst+'_BCDEF_SF'
                            col2 = 'SelMuon'+mu+'_'+syst+'_GH_SF'
                            col  = 'SelMuon'+mu+'_'+syst+'_SF'
                            self.def_modules.append( ROOT.mergeSystWeight(pair_s(col1, col2), self.era_ratios, col, "f,f->af+bf") )
            setattr(self, 'branch_defs_iter0', True )
        elif self.iteration==1 and not hasattr(self, 'branch_defs_'+self.category_weight_base+'_iter1'):
            self.def_modules.append( ROOT.getWeight('weight_'+self.category_weight_base+'_nominal', self.weight) )
            setattr(self, 'branch_defs_'+self.category_weight_base+'_iter1', True)
        elif self.iteration==2 and not hasattr(self, 'branch_defs_iter2'):
            if self.verbose: print 'branch_defs:', 'input', ' --> ', 'defs'
            self.p.branch(nodeToStart='input', nodeToEnd='defs', modules=self.def_modules)
            setattr(self, 'branch_defs_iter2', True )
        return

    """
    Branch all base categories as intermediate nodes
    """
    def _branch_base_categories(self, var, systs):
        for it in [0,1,3]:
            for c_key,c_val in self.base_categories.items():            
                if c_key.count('_')==it and not hasattr(self, 'branch_base_categories_'+c_key+'_'+var):
                    cut = c_val['cut']
                    if (it==0) and (var!='nominal') and (var in c_val['cut']):
                        _,cut_clean_OR = self._get_subcuts(c_val['cut'],var,systs)
                        cut = cut_clean_OR
                    modules = [ ROOT.getFilter( ROOT.std.string(cut)) ]
                    nodeToStart=('defs' if it==0 else c_val['category_cut_base']+'_'+var)
                    if self.verbose: print 'branch_base_categories:', nodeToStart, ' --> ', c_key+'_'+var, ('with cut: '+cut)
                    self.p.branch(nodeToStart=nodeToStart, nodeToEnd=c_key+'_'+var, modules=modules)
                    setattr(self, 'branch_base_categories_'+c_key+'_'+var, True)

    """
    Branch muon nominal
    """
    def _branch_muon_nominal(self):
        if self.iteration==0:
            pass
        elif self.iteration==1:
            pass
        elif self.iteration==2:
            modules = []
            self._branch_base_categories('nominal', [])
            if self.cut!='': 
                modules.append( ROOT.getFilter( ROOT.std.string(self.cut)) )
            modules.append( ROOT.muonHistos(self.category, 'weight_'+self.category_weight_base+'_nominal', vec_s(), "", "", False, self.verbose) )
            nodeToStart = 'defs' if self.category_cut_base=='defs' else self.category_cut_base+'_nominal'
            if self.verbose: print 'branch_muon_nominal:', nodeToStart, ' --> ', self.category+'_nominal', ('' if self.cut=='' else 'with cut: '+self.cut)
            self.p.branch(nodeToStart=nodeToStart, nodeToEnd=self.category+'_nominal', modules=modules)
        return

    """
    Branch event syst weight
    """
    def _branch_event_syst_weight(self,var, systs):
        syst_columns = vec_s()
        for syst in systs: syst_columns.push_back(var+syst)

        if self.iteration==0 and not hasattr(self, 'branch_event_syst_'+var+'_iter0'):
            self.def_modules.append( ROOT.getSystWeight(syst_columns, var+"All", "", var, pair_ui(0,0), "ff->Vnorm" ) )
            setattr(self, 'branch_event_syst_'+var+'_iter0', True )
        elif self.iteration==1:
            pass
        elif self.iteration==2:        
            modules = []
            modules.append( ROOT.muonHistos(self.category, 'weight_'+self.category_weight_base+'_nominal', syst_columns, var+'All', "", False, self.verbose) )
            if self.verbose: print 'branch_event_'+var+'_weight:', self.category+'_nominal', ' --> ', self.category+'_'+var
            self.p.branch(nodeToStart=self.category+'_nominal', nodeToEnd=self.category+'_'+var, modules=modules)
        return

    def _get_LHEScaleWeight_meaning(self,wid=0):
        if wid==0:
            return 'muR1_muF1'
        elif wid==1:
            return 'muR1_muF2'
        elif wid==2:
            return 'muR1_muF0p5'
        elif wid==3:
            return 'muR2_muF1'
        elif wid==4:
            return 'muR2_muF2'
        elif wid==5:
            return 'muR2_muF0p5'
        elif wid==6:
            return 'muR0p5_muF1'
        elif wid==7:
            return 'muR0p5_muF2'
        elif wid==8:
            return 'muR0p5_muF0p5'
        else:
            return 'muRX_muFX'

    def _get_LHEPdfWeight_meaning(self,wid=0):
        if wid<100:
            return 'NNPDF_'+str(wid)+'replica'
        elif wid==100:
            return 'NNPDF_alphaSDown'
        elif wid==101:
            return 'NNPDF_alphaSUp'
        else:
            return 'NNPDF_XXXreplica'                

    """
    Branch LHE weights
    """
    def _branch_LHE_weight(self,var, systs):

        new_weight_name = var+'_'+str(systs[0])+'_'+str(systs[1])+'All'

        if self.iteration==0 and not hasattr(self, 'branch_'+var+'_iter0'):
            syst_columns = vec_s()
            syst_columns.push_back(var)
            self.def_modules.append( ROOT.getSystWeight(syst_columns, new_weight_name, "", "", pair_ui(systs[0], systs[1]), "V->V" ) )
            setattr(self, 'branch_'+var+'_iter0', True )
        elif self.iteration==1:
            pass
        elif self.iteration==2:
            modules = []
            syst_column_names = vec_s()
            for i in range(systs[0], systs[1]+1):
                syst_column_names.push_back( ROOT.string(var+'_'+getattr(self, '_get_'+var+'_meaning')(i)) )
            modules.append( ROOT.muonHistos(self.category, 'weight_'+self.category_weight_base+'_nominal', syst_column_names, new_weight_name, "", False, self.verbose) )
            if self.verbose: print 'branch_LHE_weight: ', self.category+'_nominal', ' --> ', self.category+'_'+var
            self.p.branch(nodeToStart=self.category+'_nominal', nodeToEnd=self.category+'_'+var, modules=modules)
        return

    """
    Branch Mass weights
    """
    def _branch_mass_weight(self, systs, M, G, leptonType, scheme):

        new_weight_name = 'MassWeights_'+leptonType+'All'

        if self.iteration==0 and not hasattr(self, 'branch_mass_weight_iter0'):
            syst_columns = vec_f()
            for s in systs: syst_columns.push_back(s)
            self.def_modules.append( ROOT.getMassWeight(new_weight_name, syst_columns, float(M), float(G), leptonType, scheme) )
            setattr(self, 'branch_mass_weight_iter0', True )
        elif self.iteration==1:
            pass
        elif self.iteration==2:
            modules = []
            syst_column_names = vec_s()
            for s in systs:
                syst_column_names.push_back( ROOT.string("M"+("{:0.3f}".format(s).replace('.','p')) ) )
            modules.append( ROOT.muonHistos(self.category, 'weight_'+self.category_weight_base+'_nominal', syst_column_names, new_weight_name, "", False, self.verbose) )
            if self.verbose: print 'branch_mass_weight: ', self.category+'_nominal', ' --> ', self.category+'_mass'
            self.p.branch(nodeToStart=self.category+'_nominal', nodeToEnd=self.category+'_mass', modules=modules)
        return


    """
    Branch Fake Rate weights
    """
    def _branch_fakerate_weight(self, input_file, systs):

        new_weight_name = 'fakeRateAll'

        if self.iteration==0 and not hasattr(self, 'branch_fakerate_weight_iter0'):
            syst_columns = vec_s()
            for s in systs: syst_columns.push_back(ROOT.string(s))
            self.def_modules.append( ROOT.fakeRate(input_file, self.category, syst_columns) )
            setattr(self, 'branch_fakerate_weight_iter0', True )
        elif self.iteration==1:
            pass
        elif self.iteration==2:
            modules = []
            syst_column_names = vec_s()
            for s in systs:
                syst_column_names.push_back( ROOT.string("fakerate_"+s) )
            modules.append( ROOT.muonHistos(self.category, 'weight_'+self.category_weight_base+'_nominal', syst_column_names, new_weight_name, "", False, self.verbose) )
            if self.verbose: print 'branch_fakerate_weight: ', self.category+'_nominal', ' --> ', self.category+'_fakerate'
            self.p.branch(nodeToStart=self.category+'_nominal', nodeToEnd=self.category+'_fakerate', modules=modules)
        return


    """
    Branch muon syst scale factor
    """
    def _branch_muon_syst_scalefactor(self,var,systs):

        if var not in self.weight: return

        if self.iteration==0 and not hasattr(self, 'branch_muon_'+var+'_scalefactor_iter0'):
            syst_columns = { 'BCDEF' : vec_s(), 'GH' : vec_s() }
            for key,item in syst_columns.items():
                #for itype in ['statUp', 'statDown', 'systUp', 'systDown']:
                for itype in systs:
                    syst_columns[key].push_back('Muon_'+var+'_'+key+'_SF'+itype)                
            for key,item in syst_columns.items(): 
                mus = ['1']
                if hasattr(self,'run_DIMUON'): mus.append('2')
                for mu in mus:
                    cols = syst_columns[key]
                    col_new = "SelMuon"+mu+"_"+var+"_"+key+"_SFAll"
                    col_nom = "SelMuon"+mu+"_"+var+"_"+key+"_SF"
                    self.def_modules.append( ROOT.getSystWeight(cols, col_new, "Idx_mu"+mu, col_nom, pair_ui(0,0), "VVVV->Vnorm") )
            mus = ['1']
            if hasattr(self,'run_DIMUON'): mus.append('2')
            for mu in mus:
                col1 = 'SelMuon'+mu+'_'+var+'_BCDEF_SFAll'
                col2 = 'SelMuon'+mu+'_'+var+'_GH_SFAll'
                col_new = 'SelMuon'+mu+'_'+var+'_SFAll'
                self.def_modules.append( ROOT.mergeSystWeight(pair_s(col1,col2), self.era_ratios, col_new, "V,V->aV+bV") ) 
            if hasattr(self,'run_DIMUON'):
                col1 = 'SelMuon1_'+var+'_SFAll'
                col2 = 'SelMuon2_'+var+'_SFAll'
                col  = 'SelMuon12_'+var+'_SFAll'
                self.def_modules.append( ROOT.mergeSystWeight(pair_s(col1,col2), pair_f(1.0,1.0), col, "V,V->V*V") ) 
            setattr(self, 'branch_muon_'+var+'_scalefactor_iter0', True )
        elif self.iteration==1:
            pass
        elif self.iteration==2:
            modules = []
            syst_columns = { 'ALL' : vec_s()  }
            for key,item in syst_columns.items():
                #for type in ['statUp', 'statDown', 'systUp', 'systDown']:
                for type in systs:
                    syst_columns[key].push_back(var+'_'+type)                
            new_weight_name = "SelMuon12_"+var+"_SFAll" if 'DIMUON' in self.category else "SelMuon1_"+var+"_SFAll"
            modules.append( ROOT.muonHistos(self.category, 'weight_'+self.category_weight_base+'_nominal', syst_columns['ALL'], new_weight_name, "", False, self.verbose) )
            if self.verbose: print 'branch_muon_'+var+'_scalefactor:', self.category+'_nominal', ' --> ', self.category+'_'+var
            self.p.branch(nodeToStart=self.category+'_nominal', nodeToEnd=self.category+'_'+var, modules=modules)
        return

    """
    Create temporary RVec columns to store muon variables X that depend on <var>
    These new column names are of the form X_var_{systs}. They are needed for: 
    1) Variables that enter the cut string
    2) Variables that are plotted inside muonHistos
    """
    def _get_muon_syst_columns(self,var,systs):

        if self.recompute_vars:
            syst_columns = vec_s()
            for syst in systs: syst_columns.push_back(syst)
            Idx_mu2 = "Idx_mu2" if hasattr(self,'run_DIMUON') else ""
            if var=='corrected': 
                self.def_modules.append( ROOT.getCompVars("Idx_mu1", Idx_mu2, syst_columns, vec_s()) )
            elif var=='nom':
                self.def_modules.append( ROOT.getCompVars("Idx_mu1", Idx_mu2, vec_s(), syst_columns) )
            return

        signatureF = ""
        for i in range(len(systs)) : signatureF += "f"
        signatureF += "->V"
        signatureV = ""
        for i in range(len(systs)) : signatureV += "V"
        signatureV += "->V"

        if var=='corrected':
            for col in ['Muon_corrected_pt', 'Muon_corrected_MET_nom_mt', 'Muon_corrected_MET_nom_hpt']:    
                syst_columns = vec_s()
                for syst in systs: syst_columns.push_back( col.replace(var, syst) )            
                mus = ['1']
                if hasattr(self,'run_DIMUON'): mus.append('2')
                for mu in mus:
                    col_new = col.replace('Muon', 'SelMuon'+mu).replace(var, var+'All') 
                    self.def_modules.append( ROOT.getSystWeight( syst_columns, col_new, "Idx_mu"+mu, "", pair_ui(0,0), signatureV) )
                    
        elif var=='nom':
            # This is a duplication of code. FIXME
            for col in ['Muon_corrected_MET_nom_mt', 'Muon_corrected_MET_nom_hpt']:
                syst_columns = vec_s()
                for syst in systs: syst_columns.push_back( col.replace(var, syst) )
                mus = ['1']
                if hasattr(self,'run_DIMUON'): mus.append('2')
                for mu in mus:
                    col_new = col.replace('Muon', 'SelMuon'+mu).replace(var, var+'All') 
                    self.def_modules.append( ROOT.getSystWeight( syst_columns, col_new, "Idx_mu"+mu, "", pair_ui(0,0), signatureV) )
            for col in ['MET_nom_pt', 'MET_nom_phi']:
                syst_columns = vec_s()
                for syst in systs: syst_columns.push_back( col.replace(var, syst) )
                col_new = col.replace(var, var+'All')
                self.def_modules.append( ROOT.getSystWeight( syst_columns, col_new, "", "", pair_ui(0,0), signatureF ) )
        return

    def _get_subcuts(self,cut,var,systs):

        # 1) Remove all var-dependent variables: 'cut' -> 'cut_clean'  
        cut_clean = '('
        cut_clean += copy.deepcopy(cut)
        cut_clean_split = cut_clean.split(' && ')
        garbage = []
        for i in cut_clean_split:
            if var in i: garbage.append(i)
            for i in garbage: cut_clean = cut_clean.replace(i, '1')
        cut_clean += ')'

        # 2) Move all var-dependent variables: 'cut' \ 'cut_clean' = 'cut_removed'
        cut_removed = '(1'
        for i in garbage: cut_removed += (' && '+i)
        cut_removed += ')'

        # 3) Make the logical OR between 'cut_removed' items and AND it with 'cut_clean'
        cut_removed_OR = '(0 ' 
        for syst in systs: cut_removed_OR += ' || ('+cut_removed.replace(var, syst)+')'
        cut_removed_OR += ')' 
        cut_clean_OR = cut_clean+' && '+cut_removed_OR
        return cut_removed, cut_clean_OR

    """
    Branch RDF into final node of type muonHistos with name self.category_var. <var> is a column modifier that can affect:
    1) variables we want to plot
    2) cuts
    These cases are handled:
    A) <var> changes the event cut: create cleaned cut, removed cut, and RVec of weights as {(cut_removed)*(weight)}
    i)  If the plotted column X depends on var: Book an action via THDvarsHelper with signature <V,V>. 
    [First V is a pre-computed RVec of plotted column {X_var_systs}, second V is {(cut_removed)*(weight)} ]
    ii) Else: Book an action via THDvarsHelper with signature <f,V>
    B) <var> does not change the event cut:         
    i)  If the plotted column X depends on var: Book an action via THDvarsHelper with signature <V,f>.
    [V is a pre-computed RVec of plotted column {X_var_systs}, f is the nominal event weight} ]
    ii) Else: Book an action via THDvarsHelper with signature <f,f>
    """
    def _branch_muon_syst_column(self, var, systs):

        syst_columns = vec_s()
        for syst in systs: syst_columns.push_back( syst )

        # Get all the RVec needed
        if self.iteration==0 and not hasattr(self, 'branch_muon_syst_'+var+'_iter0'):
            self._get_muon_syst_columns(var,systs)
            setattr(self, 'branch_muon_syst_'+var+'_iter0', True )
            return

        elif self.iteration==1:
            if var in self.cut_full:
                cut_removed, _ = self._get_subcuts(self.cut_full,var,systs)  
                weight_columns = vec_s()
                for syst in systs:
                    cut_syst = cut_removed.replace(var, syst)
                    weight_cut_syst = '('+cut_syst+')*('+self.weight+')'
                    weight_cut_syst_name = 'weight_'+self.category_weight_base+'_cut_'+var+'_'+syst
                    if not hasattr(self, 'branch_muon_'+syst+'_'+var+'_'+self.category_weight_base+'_iter1'):
                        self.def_modules.append( ROOT.getWeight( ROOT.std.string(weight_cut_syst_name), ROOT.std.string(weight_cut_syst) ) )
                        setattr(self, 'branch_muon_'+syst+'_'+var+'_'+self.category_weight_base+'_iter1', True)
                    weight_columns.push_back(weight_cut_syst_name)
                signature = ""
                for i in range(len(systs)) : signature += "f"
                signature += "->V"
                if not hasattr(self, 'branch_muon_'+var+'All_'+self.category_weight_base+'_iter1'):
                    self.def_modules.append( ROOT.getSystWeight(weight_columns, 'weight_'+self.category_weight_base+'_cut_'+var+'All', "", "", pair_ui(0,0), signature) )
                    setattr(self, 'branch_muon_'+var+'All_'+self.category_weight_base+'_iter1', True)
                return
            else:
                # Nothing to be done
                return

        elif self.iteration==2:
            modules = []
            if var in self.cut_full:
                self._branch_base_categories(var,systs)
                cut = self.cut
                if self.cut_base=='':
                    _,cut_clean_OR = self._get_subcuts(self.cut,var,systs)
                    cut = cut_clean_OR
                if cut!='': 
                    modules.append( ROOT.getFilter( ROOT.std.string(cut)) )
                modules.append( ROOT.muonHistos(self.category, "", syst_columns, 'weight_'+self.category_weight_base+'_cut_'+var+'All', var, True, self.verbose ) )
                nodeToStart = 'defs' if self.category_cut_base=='defs' else self.category_cut_base+'_'+var
                if self.verbose: print 'branch_muon_'+var+'_column:', nodeToStart, ' --> ', self.category+'_'+var, ('' if cut=='' else 'with cut: '+cut )
                self.p.branch(nodeToStart=nodeToStart, nodeToEnd=self.category+'_'+var, modules=modules)
            else:                
                modules.append( ROOT.muonHistos(self.category, "weight_"+self.category_weight_base+"_nominal", syst_columns, "", var, False , self.verbose) )
                if self.verbose: print 'branch_muon_'+var+'_column:', self.category+'_nominal', ' --> ', self.category+'_'+var
                self.p.branch(nodeToStart=self.category+'_nominal', nodeToEnd=self.category+'_'+var, modules=modules)
        return

    """
    Run all modules
    """
    def run( self, categories, base_categories ):

        for key,val in categories.items():
            if 'DIMUON' in key:
                if self.verbose: print ">> ConfigRDF: run DIMUON module: precompute new columns with 'Idx2'"
                self.run_DIMUON = True            

        self.base_categories = copy.deepcopy(base_categories)

        for iteration in [0,1,2]:
            self.iteration = iteration
            if self.verbose: print "Running iteration", iteration
            for category,specifics in categories.items():  
                self.weight = specifics['weight']
                if not self.isMC: self.weight = 'Float_t(1.0)'
                self.cut = specifics['cut']
                self.cut_base = specifics['cut_base']
                self.cut_full = (self.cut_base+' && ' if self.cut_base!='' else '')+(self.cut if self.cut!='' else '')
                self.category = category                
                self.category_weight_base = specifics['category_weight_base']
                self.category_cut_base = specifics['category_cut_base']
                self._branch_defs()
                modules = specifics['modules']
                if modules.has_key('muon_nominal'): self._branch_muon_nominal()
                for key,value in modules.items():
                    if 'event_syst' in key:
                        if ('LHE' not in key) and ('mass' not in key) and ('fakerate' not in key): 
                            self._branch_event_syst_weight( key.replace('event_syst_',''), value)
                        elif 'LHE' in key: 
                            self._branch_LHE_weight( key.replace('event_syst_',''), value )
                        elif 'mass' in key:
                            self._branch_mass_weight( value['masses'], value['M'], value['G'], value['leptonType'], value['scheme'] )
                        elif 'fakerate' in key:
                            self._branch_fakerate_weight(value['input'], value['systs'])
                    elif 'muon_syst_scalefactor' in key:
                        self._branch_muon_syst_scalefactor( key.replace('muon_syst_scalefactor_',''), value )
                    elif 'muon_syst_column' in key:                         
                        self._branch_muon_syst_column( key.replace('muon_syst_column_',''), value)

                pass

        if self.verbose: print " ==>", len(self.def_modules), " defs modules have been loaded..."
        if self.verbose: print 'Get output...'
        self.p.getOutput()
        self.p.saveGraph()
        return

