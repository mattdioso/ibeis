from __future__ import absolute_import, division, print_function
import utool
from ibeis.view import viz
from ibeis.view.viz import viz_helpers as vh
from drawtool import draw_func2 as df2
from . import interact_helpers
(print, print_, printDBG, rrr, profile) = utool.inject(__name__,
                                                       '[interact_img]',
                                                       DEBUG=False)


def interact_image(ibs, gid, sel_rids=[], fnum=1,
                   select_rid_callback=None,
                   **kwargs):
    fig = interact_helpers.begin_interaction('image', fnum)

    def _image_view():
        viz.show_image(ibs, gid, sel_rids, **kwargs)
        df2.set_figtitle('Image View')

    # Create callback wrapper
    def _on_image_click(event):
        print_('[inter] clicked image')
        if interact_helpers.clicked_outside_axis(event):
            # Toggle draw lbls
            kwargs.update({
                'draw_lbls': kwargs.pop('draw_lbls', True),  # Toggle
                'select_rid_callback': select_rid_callback,
                'sel_rids': sel_rids,
            })
            interact_image(ibs, gid, **kwargs)
        else:
            ax          = event.inaxes
            viztype     = vh.get_ibsdat(ax, 'viztype')
            roi_centers = vh.get_ibsdat(ax, 'roi_centers', default=[])
            print_(' viztype=%r' % viztype)
            if len(roi_centers) == 0:
                print(' ...no chips to click')
                return
            x, y = event.xdata, event.ydata
            # Find ROI center nearest to the clicked point
            rid_list = vh.get_ibsdat(ax, 'rid_list', default=[])
            centx, _dist = utool.nearest_point(x, y, roi_centers)
            rid = rid_list[centx]
            print(' ...clicked rid=%r' % rid)
            if select_rid_callback is not None:
                select_rid_callback(gid, sel_rids=[rid])
        viz.draw()

    _image_view()
    viz.draw()
    interact_helpers.connect_callback(fig, 'button_press_event', _on_image_click)
