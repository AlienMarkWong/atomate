# coding: utf-8

from __future__ import absolute_import, division, print_function, unicode_literals

"""
This module defines a workflow for adsorption on surfaces
"""

import json
from decimal import Decimal

import numpy as np

from fireworks import FireTaskBase, Firework, FWAction, Workflow
from fireworks.utilities.fw_serializers import DATETIME_HANDLER
from fireworks.utilities.fw_utilities import explicit_serialize

from matmethods.utils.utils import env_chk, get_logger
from matmethods.vasp.database import MMDb
from matmethods.vasp.fireworks.core import OptimizeFW, TransmuterFW

from pymatgen.analysis.adsorption import generate_decorated_slabs,\
        AdsorbateSiteFinder
from pymatgen.transformations.advanced_transformations import SlabTransformation
from pymatgen.transformations.standard_transformations import SupercellTransformation
from pymatgen.transformations.site_transformations import InsertSitesTransformation
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.io.vasp.sets import MVLSlabSet, MPRelaxSet, DictSet
from pymatgen import Structure, Lattice

__author__ = 'Joseph Montoya'
__email__ = 'montoyjh@lbl.gov'

logger = get_logger(__name__)

@explicit_serialize
class PassSlabEnergy(FireTaskBase):
    """
    Placeholder just in case I need to pass something
    """

    def run_task(self, fw_spec):
        pass
        return FWAction()


@explicit_serialize
class AnalyzeAdsorption(FireTaskBase):
    """
    Analyzes the adsorption energies in a workflow
    """

    required_params = ['structure']
    optional_params = ['db_file']

    def run_task(self, fw_spec):
        pass
        """
        # Get optimized structure
        # TODO: will this find the correct path if the workflow is rerun from the start?
        optimize_loc = fw_spec["calc_locs"][0]["path"]
        logger.info("PARSING INITIAL OPTIMIZATION DIRECTORY: {}".format(optimize_loc))
        drone = VaspDrone()
        optimize_doc = drone.assimilate(optimize_loc)
        opt_struct = Structure.from_dict(optimize_doc["calcs_reversed"][0]["output"]["structure"])
        
        d = {"analysis": {}, "deformation_tasks": fw_spec["deformation_tasks"],
             "initial_structure": self['structure'].as_dict(), 
             "optimized_structure": opt_struct.as_dict()}

        # Save analysis results in json or db
        db_file = env_chk(self.get('db_file'), fw_spec)
        if not db_file:
            with open("adsorption.json", "w") as f:
                f.write(json.dumps(d, default=DATETIME_HANDLER))
        else:
            db = MMDb.from_db_file(db_file, admin=True)
            db.collection = db.db["adsorption"]
            db.collection.insert_one(d)
            logger.info("ADSORPTION ANALYSIS COMPLETE")
        return FWAction()
        """


def get_wf_adsorption(structure, adsorbate_config, vasp_input_set=None,
                      min_slab_size=7.0, min_vacuum_size=12.0, center_slab=True,
                      max_normal_search=1, slab_gen_config=None, vasp_cmd="vasp",
                      db_file=None, conventional=True, slab_incar_params={}, 
                      ads_incar_params={}, auto_dipole=True):
    """
    Returns a workflow to calculate adsorption structures and surfaces.

    Firework 1 : write vasp input set for structural relaxation,
                 run vasp,
                 pass run location,
                 database insertion.

    Firework 2 - N: Optimize Slab and Adsorbate Structures
    
    Args:
        structure (Structure): input structure to be optimized and run
        # TODO: rethink configuration 
        vasp_input_set (DictVaspInputSet): vasp input set.
        vasp_cmd (str): command to run
        db_file (str): path to file containing the database credentials.

    Returns:
        Workflow
    """
    if conventional:
        sga = SpacegroupAnalyzer(structure)
        structure = sga.get_conventional_standard_structure()
    v = vasp_input_set or MVLSlabSet(structure, bulk=True)
    if not v.incar.get("LDAU", None):
        ads_incar_params.update({"LDAU":False})
        slab_incar_params.update({"LDAU":False})
    fws = []
    fws.append(OptimizeFW(structure=structure, vasp_input_set=v,
                          vasp_cmd=vasp_cmd, db_file=db_file))

    max_index = max([int(i) for i in ''.join(adsorbate_config.keys())])
    slabs = generate_decorated_slabs(structure, max_index=max_index, 
                                     min_slab_size=min_slab_size,
                                     min_vacuum_size=min_vacuum_size, 
                                     max_normal_search=max_normal_search,
                                     center_slab=center_slab)
    mi_strings = [''.join([str(i) for i in slab.miller_index])
                  for slab in slabs]
    for key in adsorbate_config.keys():
        if key not in mi_strings:
            raise ValueError("Miller index not in generated slab list. "
                             "Unique slabs are {}".format(mi_strings))
    
    for slab in slabs:
        mi_string = ''.join([str(i) for i in slab.miller_index])
        if mi_string in adsorbate_config.keys():
            # Add the slab optimize firework
            if auto_dipole:
                weights = [site.species_and_occu.weight for site in slab]
                dipol_center = [0, 0, 0.5]
                #np.average(slab.frac_coords, axis = 1).tolist()
                dipole_dict = {"LDIPOL":"True",
                               "IDIPOL": 3,
                               "DIPOL": dipol_center}
                slab_incar_params.update(dipole_dict)
                ads_incar_params.update(dipole_dict)
            slab_trans_params = {"miller_index":slab.miller_index,
                           "min_slab_size":min_slab_size,
                           "min_vacuum_size":min_vacuum_size,
                           "shift":slab.shift,
                           "center_slab":True,
                           "max_normal_search":max_normal_search}
            slab_trans = SlabTransformation(**slab_trans_params)
            # TODO: name these more intelligently
            fw_name = "{}_{} slab optimization".format(
                slab.composition.reduced_formula, mi_string)
            vis_slab = MVLSlabSet(slab, user_incar_settings=slab_incar_params)
            fws.append(TransmuterFW(name=fw_name,
                                    structure = structure,
                                    transformations = ["SlabTransformation"],
                                    transformation_params=[slab_trans_params],
                                    copy_vasp_outputs=True,
                                    db_file=db_file,
                                    vasp_cmd=vasp_cmd,
                                    parents=fws[0],
                                    vasp_input_set = vis_slab)
                      )
            # Generate adsorbate configurations and add fws to workflow
            asf = AdsorbateSiteFinder(slab, selective_dynamics=True)
            for molecule in adsorbate_config[mi_string]:
                structures = asf.generate_adsorption_structures(molecule)
                for struct in structures:
                    struct = struct.get_sorted_structure() # This is important because InsertSites sorts the structure!
                    ads_fw_name = "{}-{}_{} adsorbate optimization".format(
                        molecule.composition.reduced_formula,
                        structure.composition.reduced_formula, mi_string)
                    # This is a bit of a hack to avoid problems with poscar/contcar conversion
                    struct.add_site_property("velocities", [[0., 0., 0.]]*struct.num_sites)
                    trans_ads = ["SlabTransformation", "SupercellTransformation", 
                                  "InsertSitesTransformation", "AddSitePropertyTransformation"]
                    trans_supercell = SupercellTransformation.from_scaling_factors(
                        round(struct.lattice.a / slab.lattice.a), 
                        round(struct.lattice.b / slab.lattice.b))
                    ads_sites = [site for site in struct if 
                                 site.properties["surface_properties"]=="adsorbate"]
                    trans_ads_params = [slab_trans_params,
                                        {"scaling_matrix":trans_supercell.scaling_matrix},
                                        {"species":[site.species_string for site in ads_sites],
                                         "coords":[site.frac_coords.tolist() # convert for proper serialization
                                                   for site in ads_sites]},
                                        {"site_properties": struct.site_properties}]
                    vis_ads = MVLSlabSet(structure, user_incar_settings = ads_incar_params)
                    fws.append(TransmuterFW(name=ads_fw_name,
                                            structure = structure,
                                            transformations = trans_ads,
                                            transformation_params = trans_ads_params,
                                            copy_vasp_outputs=True,
                                            db_file=db_file,
                                            vasp_cmd=vasp_cmd,
                                            parents=fws[0],
                                            vasp_input_set = vis_ads))
    wfname = "{}:{}".format(structure.composition.reduced_formula, "Adsorbate calculations")
    return Workflow(fws, name=wfname)

def get_wf_molecules(molecules, vasp_input_sets=None,
                     min_vacuum_size=15.0, vasp_cmd="vasp",
                     db_file=None):
    """
    Returns a workflow to calculate molecular energies as references for the
    surface workflow.

    Firework 1 : write vasp input set for structural relaxation,
                 run vasp,
                 pass run location,
                 database insertion.
    Args:
        molecules (list of molecules): input structure to be optimized and run
        # TODO: rethink configuration
        vasp_input_set (DictVaspInputSet): vasp input set.
        vasp_cmd (str): command to run
        db_file (str): path to file containing the database credentials.

    Returns:
        Workflow
    """
    fws = []
    vasp_input_sets = vasp_input_sets or [None for m in molecules]
    for molecule, vis in zip(molecules, vasp_input_sets):
        m_struct = Structure(Lattice.cubic(min_vacuum_size), molecule.species_and_occu,
                             molecule.cart_coords, coords_are_cartesian=True)
        m_struct.translate_sites(list(range(len(m_struct))),
                                 np.array([0.5]*3) - np.average(m_struct.frac_coords,axis=0))
        v = vis or MPRelaxSet(m_struct, user_incar_settings={"ISMEAR":0, 
                                                             "IBRION":5, 
                                                             "ISIF":2}) #TODO think about this
        v.config_dict["KPOINTS"].update({"reciprocal_density": 1})
        v = DictSet(m_struct, v.config_dict)

        fws.append(OptimizeFW(structure=m_struct, vasp_input_set=v,
                              vasp_cmd=vasp_cmd, db_file=db_file))
    wfname = "{}".format("Molecule calculations")
    return Workflow(fws, name=wfname)


if __name__ == "__main__":
    from fireworks import LaunchPad
    lpad = LaunchPad.auto_load()
    from pymatgen.util.testing import PymatgenTest
    from pymatgen import Molecule, MPRester
    mpr = MPRester()
    pd = mpr.get_structures("mp-2")[0]
    h2 = Molecule("HH", [[0.35, 0, 0], [-0.35, 0, 0.0]])
    adsorbate_config = {"111":[h2]}
    structure = PymatgenTest.get_structure("Si")
    wf = get_wf_adsorption(pd, adsorbate_config)
    #wf2 = get_wf_molecules([co])
