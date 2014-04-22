#!/usr/bin/env python
# TODO: ADD COPYRIGHT TAG
from __future__ import absolute_import, division, print_function
import ibeis
from os.path import join
from ibeis.injest.injest_named_folders import injest_named_folder


img_dir = join(ibeis.params.get_workdir(), 'polar_bears')
main_locals = ibeis.main(dbdir=img_dir)
ibs = main_locals['ibs']
back = main_locals.get('back', None)
injest_named_folder(ibs, img_dir)
