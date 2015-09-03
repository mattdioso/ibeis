# -*- coding: utf-8 -*-
"""
Helper module that helps expand parameters for grid search
TODO: move into custom pipe_cfg and annot_cfg modules
"""
from __future__ import absolute_import, division, print_function
import utool as ut  # NOQA
import six
import itertools
from ibeis.experiments import experiment_configs
from ibeis.experiments import cfghelpers
from ibeis.model import Config
from ibeis.init import filter_annots
print, print_, printDBG, rrr, profile = ut.inject(
    __name__, '[expt_helpers]', DEBUG=False)

QUIET = ut.QUIET


#---------------
# Big Test Cache
#-----------


def get_varied_pipecfg_lbls(cfgdict_list):
    from ibeis.model import Config
    cfg_default_dict = dict(Config.QueryConfig().parse_items())
    cfgx2_lbl = cfghelpers.get_varied_cfg_lbls(cfgdict_list, cfg_default_dict)
    return cfgx2_lbl


def get_pipecfg_list(test_cfg_name_list, ibs=None):
    r"""
    Driver function

    Returns a list of varied query configurations. Only custom configs depend on
    IBEIS. The order of the output is not gaurenteed to aggree with input order.

    Args:
        test_cfg_name_list (list):
        ibs (IBEISController):  ibeis controller object

    Returns:
        tuple: (cfg_list, cfgx2_lbl) -
            cfg_list (list): list of config objects
            cfgx2_lbl (list): denotes which parameters are being varied.
                If there is just one config then nothing is varied

    CommandLine:
        python -m ibeis.experiments.experiment_helpers --test-get_pipecfg_list
        python -m ibeis.experiments.experiment_helpers --exec-get_pipecfg_list

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.experiments.experiment_helpers import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> #test_cfg_name_list = ['best', 'custom', 'custom:sv_on=False']
        >>> #test_cfg_name_list = ['default', 'default:sv_on=False', 'best']
        >>> test_cfg_name_list = ['default', 'default:sv_on=False']
        >>> # execute function
        >>> (pcfgdict_list, pipecfg_list) = get_pipecfg_list(test_cfg_name_list, ibs)
        >>> # verify results
        >>> assert pipecfg_list[0].sv_cfg.sv_on is True
        >>> assert pipecfg_list[1].sv_cfg.sv_on is False
        >>> result = ('pipecfg_lbls = '+ ut.list_str(get_varied_pipecfg_lbls(pcfgdict_list)))
        >>> print(result)
        pipecfg_lbls = [
            'default:',
            'default:sv_on=False',
        ]
    """
    print('[expt_help.get_pipecfg_list] building pipecfg_list using: %s' % test_cfg_name_list)
    if isinstance(test_cfg_name_list, six.string_types):
        test_cfg_name_list = [test_cfg_name_list]
    _standard_cfg_names = []
    _pcfgdict_list = []
    # HACK: Parse out custom configs first
    for test_cfg_name in test_cfg_name_list:
        if test_cfg_name.startswith('custom:') or test_cfg_name == 'custom':
            print('[expthelpers] Parsing nonstandard custom config')
            if test_cfg_name.startswith('custom:'):
                # parse out modifications to custom
                cfgstr_list = ':'.join(test_cfg_name.split(':')[1:]).split(',')
                augcfgdict = ut.parse_cfgstr_list(cfgstr_list, smartcast=True)
            else:
                augcfgdict = {}
            # Take the configuration from the ibeis object
            pipe_cfg = ibs.cfg.query_cfg.deepcopy()
            # Update with augmented params
            pipe_cfg.update_query_cfg(**augcfgdict)
            # Parse out a standard cfgdict
            cfgdict = dict(pipe_cfg.parse_items())
            cfgdict['_cfgname'] = 'custom'
            cfgdict['_cfgstr'] = test_cfg_name
            _pcfgdict_list.append(cfgdict)
        else:
            _standard_cfg_names.append(test_cfg_name)
    # Handle stanndard configs next
    if len(_standard_cfg_names) > 0:
        # Get parsing information
        cfg_default_dict = dict(Config.QueryConfig().parse_items())
        valid_keys = list(cfg_default_dict.keys())
        cfgstr_list = _standard_cfg_names
        named_defaults_dict = ut.dict_subset(
            experiment_configs.__dict__, experiment_configs.TEST_NAMES)
        alias_keys = experiment_configs.ALIAS_KEYS
        # Parse standard pipeline cfgstrings
        dict_comb_list = cfghelpers.parse_cfgstr_list2(
            cfgstr_list, named_defaults_dict, cfgtype=None, alias_keys=alias_keys,
            valid_keys=valid_keys)
        # Get varied params (there may be duplicates)
        _pcfgdict_list.extend(ut.flatten(dict_comb_list))

    # Expand cfgdicts into PipelineConfig config objects
    _pipecfg_list = [Config.QueryConfig(**_cfgdict) for _cfgdict in _pcfgdict_list]

    # Enforce rule that removes duplicate configs
    # by using feasiblity from ibeis.model.Config
    # TODO: Move this unique finding code to its own function
    # and then move it up one function level so even the custom
    # configs can be uniquified
    _flag_list = ut.flag_unique_items(_pipecfg_list)
    cfgdict_list = ut.list_compress(_pcfgdict_list, _flag_list)
    pipecfg_list = ut.list_compress(_pipecfg_list, _flag_list)
    if not QUIET:
        print('[harn.help] return %d / %d unique pipeline configs' % (len(cfgdict_list), len(_pcfgdict_list)))

    if ut.get_argflag(('--pcfginfo', '--pinfo', '--pipecfginfo')):
        import sys
        ut.colorprint('Requested PcfgInfo for tests... ', 'red')
        pipecfg_lbls = get_varied_pipecfg_lbls(cfgdict_list)
        for pcfgx, (pipecfg, lbl) in enumerate(zip(pipecfg_list, pipecfg_lbls)):
            print('+--- %d / %d ===' % (pcfgx, (len(pipecfg_list))))
            ut.colorprint(lbl, 'white')
            print(pipecfg.get_cfgstr())
            print('L___')
        ut.colorprint('Finished Reporting PcfgInfo. Exiting', 'red')
        sys.exit(1)
    return (cfgdict_list, pipecfg_list)


def parse_acfg_combo_list(acfg_name_list):
    r"""
    Args:
        acfg_name_list (list):

    Returns:
        list: acfg_combo_list

    CommandLine:
        python -m ibeis.experiments.experiment_helpers --exec-parse_acfg_combo_list

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.experiments.experiment_helpers import *  # NOQA
        >>> import ibeis
        >>> from ibeis.experiments import annotation_configs
        >>> acfg_name_list = ut.get_argval(('--aidcfg', '--acfg', '-a'), type_=list, default=['default:qsize=10'])
        >>> acfg_name_list = ut.get_argval(('--aidcfg', '--acfg', '-a'), type_=list, default=['default;uncontrolled'])
        >>> acfg_combo_list = parse_acfg_combo_list(acfg_name_list)
        >>> acfg_list = ut.flatten(acfg_combo_list)
        >>> printkw = dict()
        >>> annotation_configs.print_acfg_list(acfg_list, **printkw)
    """
    from ibeis.experiments import annotation_configs
    named_defaults_dict = ut.dict_take(annotation_configs.__dict__, annotation_configs.TEST_NAMES)
    named_qcfg_defaults = dict(zip(annotation_configs.TEST_NAMES, ut.get_list_column(named_defaults_dict, 'qcfg')))
    named_dcfg_defaults = dict(zip(annotation_configs.TEST_NAMES, ut.get_list_column(named_defaults_dict, 'dcfg')))
    alias_keys = annotation_configs.ALIAS_KEYS
    # need to have the cfgstr_lists be the same for query and database so they can be combined properly for now
    qcfg_combo_list = cfghelpers.parse_cfgstr_list2(
        cfgstr_list=acfg_name_list, named_defaults_dict=named_qcfg_defaults,
        cfgtype='qcfg', alias_keys=alias_keys, expand_nested=False)
    dcfg_combo_list = cfghelpers.parse_cfgstr_list2(
        acfg_name_list, named_dcfg_defaults, 'dcfg', alias_keys=alias_keys,
        expand_nested=False)

    acfg_combo_list = []
    for qcfg_combo, dcfg_combo in zip(qcfg_combo_list, dcfg_combo_list):
        acfg_combo = [
            dict([('qcfg', qcfg), ('dcfg', dcfg)])
            for qcfg, dcfg in list(itertools.product(qcfg_combo, dcfg_combo))
        ]
        acfg_combo_list.append(acfg_combo)
    return acfg_combo_list


def get_annotcfg_list(ibs, acfg_name_list, filter_dups=True):
    r"""
    For now can only specify one acfg name list

    TODO: move to filter_annots

    Args:
        annot_cfg_name_list (list):

    CommandLine:
        python -m ibeis.experiments.experiment_helpers --exec-get_annotcfg_list:0
        python -m ibeis.experiments.experiment_helpers --exec-get_annotcfg_list:1
        python -m ibeis.experiments.experiment_helpers --exec-get_annotcfg_list:2

        python -m ibeis.experiments.experiment_helpers --exec-get_annotcfg_list:0 --db NNP_Master3 -a viewpoint_compare --nocache-aid --verbtd
        python -m ibeis.experiments.experiment_helpers --exec-get_annotcfg_list:0 --db PZ_ViewPoints -a viewpoint_compare --nocache-aid --verbtd

    Example0:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.experiments.experiment_helpers import *  # NOQA
        >>> import ibeis
        >>> from ibeis.experiments import annotation_configs
        >>> ibs = ibeis.opendb(defaultdb='PZ_MTEST')
        >>> filter_dups = not ut.get_argflag('--nofilter-dups')
        >>> #acfg_name_list = ut.get_argval(('--aidcfg', '--acfg', '-a'), type_=list, default=['default:qsize=10'])
        >>> acfg_name_list = ut.get_argval(('--aidcfg', '--acfg', '-a'), type_=list, default=['default'])
        >>> acfg_list, expanded_aids_list = get_annotcfg_list(ibs, acfg_name_list, filter_dups)
        >>> print('\n PRINTING TEST RESULTS')
        >>> result = ut.list_str(acfg_list, nl=3)
        >>> print('\n')
        >>> printkw = dict(combined=True, per_name_vpedge=None, per_qual=False, per_vp=False)
        >>> annotation_configs.print_acfg_list(acfg_list, expanded_aids_list, ibs, **printkw)
    """
    print('[harn.help] building acfg_list using %r' % (acfg_name_list,))
    from ibeis.experiments import annotation_configs
    acfg_combo_list = parse_acfg_combo_list(acfg_name_list)

    #acfg_slice = ut.get_argval('--acfg_slice', type_=slice, default=None)
    # Sliceing happens before expansion (dependenceis get)
    combo_slice = ut.get_argval('--combo_slice', type_='fuzzy_subset', default=slice(None))
    acfg_combo_list = [ut.list_take(acfg_combo_, combo_slice) for acfg_combo_ in acfg_combo_list]

    if ut.get_argflag('--consistent'):
        # Expand everything as one consistent annot list
        acfg_combo_list = [ut.flatten(acfg_combo_list)]

    #expanded_aids_list = [filter_annots.expand_acfgs(ibs, acfg) for acfg in acfg_list]
    expanded_aids_combo_list = [
        filter_annots.expand_acfgs_consistently(ibs, acfg_combo_) for acfg_combo_ in acfg_combo_list
    ]
    expanded_aids_combo_flag_list = ut.flatten(expanded_aids_combo_list)
    acfg_list = ut.get_list_column(expanded_aids_combo_flag_list, 0)
    expanded_aids_list = ut.get_list_column(expanded_aids_combo_flag_list, 1)

    # Sliceing happens after expansion (but the labels get screwed up)
    acfg_slice = ut.get_argval('--acfg_slice', type_='fuzzy_subset', default=None)
    if acfg_slice is not None:
        acfg_list = ut.list_take(acfg_list, acfg_slice)
        expanded_aids_list = ut.list_take(expanded_aids_list, acfg_slice)

    # Hack: Override qaids
    _qaids = ut.get_argval('--qaid', type_=list, default=None)
    if _qaids is not None:
        # Override qaid_list?
        expanded_aids_list = [(_qaids, daids) for qaids, daids in expanded_aids_list]

    if filter_dups:
        acfg_list_ = []
        expanded_aids_list_ = []
        seen_ = ut.ddict(list)
        for acfg, (qaids, daids) in zip(acfg_list, expanded_aids_list):
            key = (ut.hashstr_arr27(qaids, 'qaids'), ut.hashstr_arr27(daids, 'daids'))
            if key in seen_:
                seen_[key].append(acfg)
                continue
            else:
                seen_[key].append(acfg)
                expanded_aids_list_.append((qaids, daids))
                acfg_list_.append(acfg)
        if ut.NOT_QUIET:
            duplicate_configs = dict([(key_, val_) for key_, val_ in seen_.items() if len(val_) > 1])
            if len(duplicate_configs) > 0:
                print('The following configs produced duplicate annnotation configs')
                for key, val in duplicate_configs.items():
                    nonvaried_compressed_dict, varied_compressed_dict_list = annotation_configs.compress_acfg_list_for_printing(val)
                    print('+--')
                    print('key = %r' % (key,))
                    print('varied_compressed_dict_list = %s' % (ut.list_str(varied_compressed_dict_list),))
                    print('nonvaried_compressed_dict = %s' % (ut.dict_str(nonvaried_compressed_dict),))
                    print('L__')

            print('[harn.help] parsed %d / %d unique annot configs' % (len(acfg_list_), len(acfg_list)))
        acfg_list = acfg_list_
        expanded_aids_list = expanded_aids_list_

    if ut.get_argflag(('--acfginfo', '--ainfo', '--aidcfginfo')):
        import sys
        ut.colorprint('[experiment_helpers] Requested AcfgInfo ... ', 'red')
        print('combo_slice = %r' % (combo_slice,))
        print('acfg_slice = %r' % (acfg_slice,))
        annotation_configs.print_acfg_list(acfg_list, expanded_aids_list, ibs)
        ut.colorprint('[experiment_helpers] exiting due to AcfgInfo info request', 'red')
        sys.exit(1)

    return acfg_list, expanded_aids_list


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.experiments.experiment_helpers
        python -m ibeis.experiments.experiment_helpers --allexamples
        python -m ibeis.experiments.experiment_helpers --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
