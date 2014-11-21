# flake8: noqa
from __future__ import absolute_import, division, print_function
from ibeis.model.preproc import preproc_chip
from ibeis.model.preproc import preproc_detectchip
from ibeis.model.preproc import preproc_detectimg
from ibeis.model.preproc import preproc_encounter
from ibeis.model.preproc import preproc_feat
from ibeis.model.preproc import preproc_featweight
from ibeis.model.preproc import preproc_image
from ibeis.model.preproc import preproc_probchip
from ibeis.model.preproc import preproc_residual
from ibeis.model.preproc import preproc_rvec
import utool
print, print_, printDBG, rrr, profile = utool.inject(
    __name__, '[ibeis.model.preproc]')


def reload_subs(verbose=True):
    """ Reloads ibeis.model.preproc and submodules """
    rrr(verbose=verbose)
    getattr(preproc_chip, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(preproc_detectchip, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(preproc_detectimg, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(preproc_encounter, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(preproc_feat, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(preproc_featweight, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(preproc_image, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(preproc_probchip, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(preproc_residual, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(preproc_rvec, 'rrr', lambda verbose: None)(verbose=verbose)
    rrr(verbose=verbose)
    try:
        # hackish way of propogating up the new reloaded submodule attributes
        reassign_submodule_attributes(verbose=verbose)
    except Exception as ex:
        print(ex)
rrrr = reload_subs

IMPORT_TUPLES = [
    ('preproc_chip', None, False),
    ('preproc_detectchip', None, False),
    ('preproc_detectimg', None, False),
    ('preproc_encounter', None, False),
    ('preproc_feat', None, False),
    ('preproc_featweight', None, False),
    ('preproc_image', None, False),
    ('preproc_probchip', None, False),
    ('preproc_residual', None, False),
    ('preproc_rvec', None, False),
]
"""
Regen Command:
    cd /home/joncrall/code/ibeis/ibeis/model/preproc
    makeinit.py
"""
# autogenerated __init__.py for: '/home/joncrall/code/ibeis/ibeis/model/preproc'
