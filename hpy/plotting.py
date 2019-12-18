"""
hpy.plotting.py
~~~~~~~~~~~~~~~~

Contains plotting functions

"""

# standard imports
from copy import deepcopy

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import logging
import warnings

# third party imports
from matplotlib.axes import Axes
from matplotlib import patches
from matplotlib.animation import FuncAnimation
from matplotlib.legend import Legend
from colour import Color
from scipy import stats
from collections import Mapping

try:
    from IPython.core.display import HTML
except ImportError:
    HTML = None

# local imports
from hpy.main import export, concat_cols, is_list_like, floor_signif, ceil_signif, tprint, list_intersection
from hpy.ds import get_df_corr, lfit, kde, df_count, quantile_split, top_n_coding, df_rmsd, df_agg

# colors for plotting

# --- constants

rcParams = {
    'palette': [
        'xkcd:blue', 'xkcd:red', 'xkcd:green', 'xkcd:cyan', 'xkcd:magenta',
        'golden yellow', 'xkcd:dark cyan', 'xkcd:red orange', 'xkcd:dark yellow', 'xkcd:easter green',
        'baby blue', 'xkcd:light brown', 'xkcd:strong pink', 'xkcd:light navy blue', 'xkcd:deep blue',
        'deep red', 'xkcd:ultramarine blue', 'xkcd:sea green', 'xkcd:plum', 'xkcd:old pink',
        'lawn green', 'xkcd:amber', 'xkcd:green blue', 'xkcd:yellow green', 'xkcd:dark mustard',
        'bright lime', 'xkcd:aquamarine', 'xkcd:very light blue', 'xkcd:light grey blue', 'xkcd:dark sage',
        'dark peach', 'xkcd:shocking pink'
    ],
    'hatches': ['/', '\\', '|', '-', '+', 'x', 'o', 'O', '.', '*'],
    'figsize_square': (8, 8),
    'fig_width': 8,
    'fig_height': 8
}

# # loop
# for _i in range(5):
#     rcParams['palette'] += rcParams['palette']
#     rcParams['hatches'] += rcParams['hatches']


# --- functions
@export
def heatmap(x: str, y: str, z: str, data: pd.DataFrame, figsize: tuple = rcParams['figsize_square'], ax: Axes = None,
            cmap: object = None, invert_y: bool = True, **kwargs) -> Axes:
    """
        wrapper for seaborn heatmap in x-y-z format
    :param x: Variable name for x axis value
    :param y: Variable name for y axis value
    :param z: Variable name for z value, used to color the heatmap
    :param data: Data Frame or similar containing the named data
    :param figsize: Size of the generated figure
    :param ax: Axes object to plot on. If None a new axes of size figsize is generated
    :param cmap: Color map to use
    :param invert_y: Weather to call ax.invert_yaxis (orders the heatmap as expected)
    :param kwargs: Other keyword arguments passed to seaborn heatmap
    :return: The Axes object with the plot on it
    """
    if cmap is None:
        cmap = sns.diverging_palette(10, 220, as_cmap=True)

    _df = data.groupby([x, y]).agg({z: 'mean'}).reset_index().pivot(x, y, z)

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    sns.heatmap(_df, ax=ax, cmap=cmap, **kwargs)
    ax.set_title(z)

    if invert_y:
        ax.invert_yaxis()

    return ax


def corrplot(data, width=1, annotations=True, number_format='.2f', ax=None):
    """
        function to create a correlation plot using a seaborn heatmap
        based on: https://www.linkedin.com/pulse/generating-correlation-heatmaps-seaborn-python-andrew-holt
    :param number_format: The format string used for the annotations
    :param data: Data Frame or similar containing the named data
    :param width: Width of each individual cell in the corrplot
    :param annotations: whether to annotate the corrplot with the correlation coefficients
    :param ax: The Axes object to draw on. If None a new one is generated
    :return: The Axes object with the plot on it
    """
    # Create Correlation df
    _corr = data.corr()

    _size = len(_corr) * width

    # Plot figsize
    if ax is None:
        _, ax = plt.subplots(figsize=(_size, _size))
    # Generate Color Map
    _colormap = sns.diverging_palette(220, 10, as_cmap=True)

    # mask
    _mask = np.zeros_like(_corr)
    _mask[np.triu_indices_from(_mask)] = True

    # Generate Heat Map, allow annotations and place floats in map
    sns.heatmap(_corr, cmap=_colormap, annot=annotations, fmt=number_format, mask=_mask, ax=ax)

    # Adjust tick labels
    ax.set_xticks(ax.get_xticks()[:-1])
    _yticklabels = ax.get_yticklabels()[1:]
    ax.set_yticks(ax.get_yticks()[1:])
    ax.set_yticklabels(_yticklabels)

    return ax


# print a bar corrplot
def corrplot_bar(data, target=None, columns=None, corr_cutoff=0, corr_as_alpha=False, fix_x_range=True, ax=None,
                 figsize=(10, 10)):
    _df_corr = get_df_corr(data, target=target)
    _df_corr = _df_corr[_df_corr['corr_abs'] >= corr_cutoff]

    if target is None:
        _df_corr['label'] = concat_cols(_df_corr, ['col_0', 'col_1'], sep=' X ')
    else:
        _df_corr['label'] = _df_corr['col_1']

    # filter columns (if applicable)
    if columns is not None:
        _columns = columns + []
        if target is not None and target not in _columns:
            _columns.append(target)
        _df_corr = _df_corr[(_df_corr['col_0'].isin(_columns)) & (_df_corr['col_1'].isin(_columns))]

    # get colors
    _rgba_colors = np.zeros((len(_df_corr), 4))

    # for red the first column needs to be one
    _rgba_colors[:, 0] = np.where(_df_corr['corr'] > 0., 0., 1.)
    # for blue the third column needs to be one
    _rgba_colors[:, 2] = np.where(_df_corr['corr'] > 0., 1., 0.)
    # the fourth column needs to be alphas
    if corr_as_alpha:
        _rgba_colors[:, 3] = _df_corr['corr_abs'].where(lambda _: _ > .1, .1)
    else:
        _rgba_colors[:, 3] = 1

    # _df_corr['color'] = np.where(_df_corr['corr']>0,'blue','red')

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    _rgba_colors = np.round(_rgba_colors, 2)

    _plot = ax.barh(_df_corr['label'], _df_corr['corr'], color=_rgba_colors)  # ,palette='RdBu_r'
    # sns.barplot(x='corr',y='label',palette='RdBu_r',data=_df_corr)
    ax.invert_yaxis()

    if fix_x_range:
        ax.set_xlim([-1, 1])

    if target is not None:
        ax.set_title('Correlations with {} by Absolute Value'.format(target))
        ax.set_xlabel('corr × {}'.format(target))
    else:
        ax.set_title('Correlations by Absolute Value')

    if ax is None:
        plt.gcf().patch.set_facecolor('white')
        plt.show()
    else:
        return ax


# print a pairwise_corrplot to for all variables in the df, by default only plots those with a correlation 
# coefficient of >= .5
def pairwise_corrplot(df, corr_cutoff=.5, ncols=4, hue=None, width=rcParams['fig_width'],
                      height=rcParams['fig_height'], trendline=True, alpha=.5, ax=None,
                      target=None, palette=rcParams['palette'],
                      max_n=1000, random_state=None, sample_warn=True, return_fig_ax=False, **kwargs):
    warnings.simplefilter('ignore', np.RankWarning)

    # actual plot function
    def _f_plot(_f_x, _f_y, _f_data, _f_color, _f_color_trendline, _f_label, _f_ax):

        _data = _f_data.copy()

        # limit plot points
        if max_n is not None:
            if len(_data) > max_n:
                if sample_warn:
                    warnings.warn(
                        'Limiting Scatter Plot to {:,} randomly selected points. '
                        'Turn this off with max_n=None or suppress this warning with sample_warn=False.'.format(
                            max_n))
                _data = _data.sample(max_n, random_state=random_state)

        _f_ax.scatter(_f_x, _f_y, data=_data, alpha=alpha, color=_f_color, label=_f_label)

        if trendline:
            _f_ax.plot(_f_data[_f_x], lfit(_f_data[_f_x], _f_data[_f_y]), color=_f_color_trendline, linestyle=':')

        return _f_ax

    # avoid inplace operations
    _df = df.copy()
    _df_hues = pd.DataFrame()
    _df_corrs = pd.DataFrame()
    _hues = None

    if hue is not None:
        _hues = _df[hue].value_counts().reset_index()['index']
        _df_hues = {}
        _df_corrs = {}

        for _hue in _hues:
            _df_hue = _df[_df[hue] == _hue]
            _df_corr_hue = get_df_corr(_df_hue, target=target)

            _df_hues[_hue] = _df_hue.copy()
            _df_corrs[_hue] = _df_corr_hue.copy()

    # get df corr
    _df_corr = get_df_corr(_df, target=target)

    if corr_cutoff is not None:
        _df_corr = _df_corr[_df_corr['corr_abs'] >= corr_cutoff]

    # warning for empty df
    if len(_df_corr) == 0:
        warnings.warn('Correlation DataFrame is Empty. Do you need a lower corr_cutoff?')
        return None

    # edge case for less plots than ncols
    if len(_df_corr) < ncols:
        _ncols = len(_df_corr)
    else:
        _ncols = ncols

    # calculate nrows
    _nrows = int(np.ceil(len(_df_corr) / _ncols))

    figsize = (width * ncols, height * _nrows)

    if ax is None:
        fig, ax = plt.subplots(nrows=_nrows, ncols=_ncols, figsize=figsize, **kwargs)
    else:
        fig = plt.gcf()

    _row = None
    _col = None

    for _it in range(len(_df_corr)):

        _col = _it % _ncols
        _row = _it // _ncols

        _x = _df_corr.iloc[_it]['col_1']
        _y = _df_corr.iloc[_it]['col_0']  # so that target (if available) becomes y
        _corr = _df_corr.iloc[_it]['corr']

        if _ncols == 1:
            _rows_prio = True
        else:
            _rows_prio = False

        _ax = get_subax(ax, _row, _col, rows_prio=_rows_prio)

        _ax.set_xlabel(_x)
        _ax.set_ylabel(_y)
        _ax.set_title('corr = {:.3f}'.format(_corr))

        # hue if
        if hue is None:

            # actual plot
            _f_plot(_f_x=_x, _f_y=_y, _f_data=_df, _f_color=None, _f_color_trendline='k', _f_label=None, _f_ax=_ax)

        else:

            for _hue_i in range(len(_hues)):

                _hue = _hues[_hue_i]
                _color = palette[_hue_i]

                _df_hue = _df_hues[_hue]
                _df_corr_hue = _df_corrs[_hue].copy()

                # sometimes it can happen that the correlation is not possible to calculate because
                # one of those values does not change in the hue level
                # i.e. use try except

                try:
                    _df_corr_hue = _df_corr_hue[_df_corr_hue['col_1'] == _x]
                    _df_corr_hue = _df_corr_hue[_df_corr_hue['col_0'] == _y]
                    _corr_hue = _df_corr_hue['corr'].iloc[0]
                except ValueError:
                    _corr_hue = 0

                # actual plot
                _f_plot(_f_x=_x, _f_y=_y, _f_data=_df_hue, _f_color=_color, _f_color_trendline=_color,
                        _f_label='{} corr: {:.3f}'.format(_hue, _corr_hue), _f_ax=_ax)

                _ax.legend()

    # hide unused axis
    for __col in range(_col + 1, _ncols):
        get_subax(ax, _row, __col, rows_prio=False).set_axis_off()

    if return_fig_ax:
        return fig, ax
    else:
        plt.tight_layout()
        fig.patch.set_facecolor('white')
        plt.show()


# plot a NORMALIZED histogram + a fit of a gaussian distribution
def distplot(x, data=None, hue=None, hue_order=None, pattern=None, hue_labels=None, hue_sort_type='count',
             hue_round=1, face_color='cyan', gauss_color='black', edgecolor='gray', alpha=None, bins=40, perc=None,
             top_nr=5, other_name='other', title=True, title_prefix='', value_name='column_value',
             sigma_cutoff=3, figsize=plt.rcParams['figure.figsize'], show_hist=True, distfit='kde', show_grid=False,
             legend=True, legend_loc='bottom', legend_space=None, legend_ncol=1, agg_func='mean',
             number_format='.2f', kde_steps=1000, max_n=100000, random_state=None, sample_warn=True, xlim=None,
             distfit_line=None, label_style='mu_sigma', ax=None, **kwargs):
    if pattern is None:
        pattern = rcParams['palette']
    if not top_nr:
        top_nr = None

    if data is None:

        if 'name' in dir(x):
            _x = x.name
            _x_name = _x
        else:
            _x = 'x'
            _x_name = None

        _df = pd.DataFrame.from_dict({_x: x})

    else:

        _df = data.copy()  # avoid inplace operations
        del data

        if is_list_like(x):

            _df = pd.melt(_df, value_vars=x, value_name=value_name)
            _x = value_name
            _x_name = _x
            hue = 'variable'
            hue_order = x

        else:

            _x = x
            _x_name = _x

    del x

    if hue is not None:

        _df = _df[~_df[hue].isnull()]
        if hue_round is not None:
            if _df[hue].dtype == float:
                _df[hue] = _df[hue].round(hue_round)
        if perc is None:
            perc = True

    else:

        if perc is None:
            perc = False

    # in case that there are more than max_n samples: take  a random sample for calc speed
    if max_n:
        if len(_df) > max_n:
            if sample_warn:
                warnings.warn(
                    'Limiting samples to {:,} for calc speed. Turn this off with max_n=None or suppress this warning '
                    'with sample_warn=False.'.format(max_n))
            _df = _df.sample(max_n, random_state=random_state)

    if alpha is None:

        if hue is None:
            alpha = .75
        else:
            alpha = .5

    # the actual plot
    def _f_distplot(_f_x, _f_data, _f_x_label, _f_facecolor, _f_distfit_color, _f_bins,
                              _f_sigma_cutoff, _f_xlim, _f_distfit_line, _f_ax, _f_ax2):

        # make a copy to avoid inplace operations
        _df_i = _f_data.copy()

        # rename hues (if applicable)
        if hue_labels is not None:
            _df_i[hue] = _df_i[hue].replace(hue_labels)

        # best fit of data
        _mu = _df_i.agg({_f_x: agg_func})[0]
        _sigma = _df_i.agg({_f_x: 'std'})[0]

        # apply sigma cutoff
        if (_f_sigma_cutoff is not None) or (_f_xlim is not None):

            if _f_xlim is not None:

                __x_min = _f_xlim[0]
                __x_max = _f_xlim[1]

            elif is_list_like(_f_sigma_cutoff):

                __x_min = _f_sigma_cutoff[0]
                __x_max = _f_sigma_cutoff[1]

            else:

                __x_min = _mu - _f_sigma_cutoff * _sigma
                __x_max = _mu + _f_sigma_cutoff * _sigma

            _df_i = _df_i[
                (_df_i[_f_x] >= __x_min) &
                (_df_i[_f_x] <= __x_max)
                ]

        # the histogram of the data

        try:
            _mu_label = format(_mu, number_format)
        except ValueError:
            _mu_label = '0'

        try:
            _sigma_label = format(_sigma, number_format)
        except ValueError:
            _sigma_label = '0'

        if agg_func == 'mean':
            _mu_symbol = r'\ \mu'
        else:
            _mu_symbol = r'\ \nu'

        if label_style == 'mu_sigma':
            _label = r'{}: $ {}={},\ \sigma={}$'.format(_f_x_label, _mu_symbol, _mu_label, _sigma_label)
        else:
            _label = _f_x_label

        if show_hist:
            _hist_n, _hist_bins = _f_ax.hist(_df_i[_f_x], _f_bins, density=perc, facecolor=_f_facecolor,
                                             edgecolor=edgecolor,
                                             alpha=alpha, label=_label)[:2]
            _label_2 = '__nolegend___'
            if _f_distfit_line is None:
                _f_distfit_line = '--'
        else:
            _hist_n = None
            _hist_bins = None
            _label_2 = _label + ''
            if _f_distfit_line is None:
                _f_distfit_line = '-'

        if distfit is not None:

            if show_hist:
                _ax = _f_ax2
            else:
                _ax = _f_ax

            if distfit == 'gauss':

                # add a 'best fit' line
                _y = stats.norm.pdf(_f_bins, _mu, _sigma)  # _hist_bins
                _ax.plot(_f_bins, _y, linestyle=_f_distfit_line, color=_f_distfit_color, alpha=alpha, linewidth=2,
                         label=_label_2, **kwargs)

                if show_hist:
                    _ax.set_ylim([0, np.max(_y) * 1.05])  # there used to be a try except here

            elif distfit == 'kde':

                _kde = kde(x=_f_x, df=_df_i, x_steps=kde_steps)[0]
                __x = _kde[_f_x]
                _y = _kde['value']
                _ax.plot(__x, _y, linestyle=_f_distfit_line, color=_f_distfit_color, alpha=alpha, linewidth=2,
                         label=_label_2, **kwargs)

            _f_ax2.get_yaxis().set_visible(False)

        if perc and show_hist:

            _y_max = np.max(_hist_n) / np.sum(_hist_n) * 100
            _y_ticklabels = list(_f_ax.get_yticks())
            _y_ticklabels = [float(_) for _ in _y_ticklabels]

            _factor = _y_max / np.nanmax(_y_ticklabels)
            if np.isnan(_factor):
                _factor = 1
            _y_ticklabels = [format(int(_ * _factor), ',') for _ in _y_ticklabels]
            _f_ax.set_yticklabels(_y_ticklabels)
            _f_ax.set_ylabel('%')

        elif show_hist:

            _f_ax.set_ylabel('count')

            # adjust xlims if necessary
            _xlim = list(_f_ax.get_xlim())

            # here _df is used to access the 'parent' DataFrame with all hue levels
            if _xlim[0] <= _plot_x_min:
                _xlim[0] = _plot_x_min
            if _xlim[1] >= _plot_x_max:
                _xlim[1] = _plot_x_max

            _f_ax.set_xlim(_xlim)

        return _f_ax, _f_ax2

    # preparing the data frame

    # drop nan values
    _df = _df[np.isfinite(_df[_x])]

    # init plot
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    ax2 = ax.twinx()

    # hue case
    if hue is None:

        if xlim is not None:

            _x_min = xlim[0]
            _x_max = xlim[1]

        elif sigma_cutoff is not None:

            _x_min = _df[_x].mean() - _df[_x].std() * sigma_cutoff
            _x_max = _df[_x].mean() + _df[_x].std() * sigma_cutoff

        else:

            _x_min = _df[_x].min()
            _x_max = _df[_x].max()

        if not is_list_like(bins):
            _x_step = (_x_max - _x_min) / bins
            _bins = np.arange(_x_min, _x_max + _x_step, _x_step)

            _plot_x_min = _df[_x].min() - _x_step
            _plot_x_max = _df[_x].max() + _x_step
        else:
            _bins = bins
            _plot_x_min = np.min(bins)
            _plot_x_max = np.max(bins)

        # just plot
        ax, ax2 = _f_distplot(_f_x=_x, _f_data=_df, _f_x_label=_x_name, _f_facecolor=face_color,
                                        _f_distfit_color=gauss_color,
                                        _f_bins=_bins, _f_sigma_cutoff=sigma_cutoff,
                                        _f_xlim=xlim, _f_distfit_line=distfit_line, _f_ax=ax, _f_ax2=ax2)

    else:

        _df[hue] = _df[hue].astype('str')

        # make one plot per hue, but all on the same axis
        if hue_order is None:

            # sort by value count
            if hue_sort_type == 'count':
                _hues = list(_df[hue].value_counts().reset_index()['index'])
            else:
                _hues = sorted(_df[hue].unique())

            # group values outside of top_n to other_name
            if top_nr is not None:

                if (top_nr + 1) < len(_hues):  # the plus 1 is there to avoid the other group having exactly 1 entry

                    _hues = pd.Series(_hues)[0:top_nr]
                    _df[hue] = np.where(_df[hue].isin(_hues), _df[hue], other_name)
                    _df[hue] = _df[hue].astype('str')
                    _hues = list(_hues) + [other_name]

        else:
            _hues = hue_order

        # find shared _x_min ; _x_max

        if xlim is not None:

            _sigma_cutoff_hues = None

            _x_min = xlim[0]
            _x_max = xlim[1]

        elif sigma_cutoff is None:

            _sigma_cutoff_hues = None

            _x_min = _df[_x].min()
            _x_max = _df[_x].max()

        else:
            _df_agg = _df.groupby(hue).agg({_x: ['mean', 'std']}).reset_index()
            _df_agg.columns = [hue, 'mean', 'std']
            _df_agg['x_min'] = _df_agg['mean'] - _df_agg['std'] * sigma_cutoff
            _df_agg['x_max'] = _df_agg['mean'] + _df_agg['std'] * sigma_cutoff
            _df_agg['x_range'] = _df_agg['x_max'] - _df_agg['x_min']

            _x_min = _df_agg['x_min'].min()
            _x_max = _df_agg['x_max'].max()

            _sigma_cutoff_hues = [_x_min, _x_max]

        _x_step = (_x_max - _x_min) / bins

        _plot_x_min = _df[_x].min() - _x_step
        _plot_x_max = _df[_x].max() + _x_step

        _bins = np.arange(_x_min, _x_max + _x_step, _x_step)

        for _it in range(len(_hues)):

            _hue = _hues[_it]

            if isinstance(pattern, Mapping):
                _color = pattern[_hue]
            elif is_list_like(pattern):
                _color = pattern[_it]
            else:
                _color = pattern

            if isinstance(distfit_line, Mapping):
                _linestyle = distfit_line[_hue]
            elif is_list_like(distfit_line):
                _linestyle = distfit_line[_it]
            else:
                _linestyle = distfit_line

            _df_hue = _df[_df[hue] == _hue]

            ax, ax2 = _f_distplot(_f_x=_x, _f_data=_df_hue, _f_x_label=_hue, _f_facecolor=_color,
                                            _f_distfit_color=_color, _f_bins=_bins,
                                            _f_sigma_cutoff=_sigma_cutoff_hues,
                                            _f_xlim=xlim, _f_distfit_line=_linestyle, _f_ax=ax, _f_ax2=ax2)
    if legend:

        if legend_loc in ['bottom', 'right']:
            legend_outside(ax, loc=legend_loc, legend_space=legend_space, ncol=legend_ncol)
            legend_outside(ax2, loc=legend_loc, legend_space=legend_space, ncol=legend_ncol)
        else:
            _, _labels = ax.get_legend_handles_labels()
            if len(_labels) > 0:
                ax.legend(loc=legend_loc, ncol=legend_ncol)

            _, _labels = ax2.get_legend_handles_labels()
            if len(_labels) > 0:
                ax2.legend(loc=legend_loc, ncol=legend_ncol)

    # postprocessing

    if title:
        ax.set_title('{}{}'.format(title_prefix, _x_name))
    if xlim is not None:
        ax.set_xlim(xlim)

    if show_grid:
        ax.grid(True)

    return ax


# 2d histogram
def hist_2d(x, y, data, bins=100, std_cutoff=3, cutoff_perc=.01, cutoff_abs=0, cmap='rainbow', ax=None,
            figsize=(10, 10), color_sigma='xkcd:red', draw_sigma=True, **kwargs):
    _df = data.copy()
    del data

    if std_cutoff is not None:
        _x_min = _df[x].mean() - _df[x].std() * std_cutoff
        _x_max = _df[x].mean() + _df[x].std() * std_cutoff
        _y_min = _df[y].mean() - _df[y].std() * std_cutoff
        _y_max = _df[y].mean() + _df[y].std() * std_cutoff

        # x or y should be in std range
        _df = _df[
            ((_df[x] >= _x_min) & (_df[x] <= _x_max) &
             (_df[y] >= _y_min) & (_df[y] <= _y_max))
        ].reset_index(drop=True)

    _x = _df[x]
    _y = _df[y]

    # Estimate the 2D histogram
    _hist, _x_edges, _y_edges = np.histogram2d(_x, _y, bins=bins)

    # hist needs to be rotated and flipped
    _hist = np.rot90(_hist)
    _hist = np.flipud(_hist)

    # Mask too small counts
    if cutoff_abs is not None:
        _hist = np.ma.masked_where(_hist <= cutoff_abs, _hist)
    if cutoff_perc is not None:
        _hist = np.ma.masked_where(_hist <= _hist.max() * cutoff_perc, _hist)

    # Plot 2D histogram using pcolor
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    _mappable = ax.pcolormesh(_x_edges, _y_edges, _hist, cmap=cmap, **kwargs)
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    _cbar = plt.colorbar(mappable=_mappable, ax=ax)
    _cbar.ax.set_ylabel('count')

    # draw ellipse to mark 1 sigma area
    if draw_sigma:
        _ellipse = patches.Ellipse(xy=(_x.median(), _y.median()), width=_x.std(), height=_y.std(),
                                   edgecolor=color_sigma, fc='None', lw=2, ls=':')
        ax.add_patch(_ellipse)

    return ax


def paired_plot(df_in, vars_in, color_in=None, cmap_in=None, alpha_in=1, **kwargs):
    # Function to calculate correlation coefficient between two arrays
    def _f_corr(_f_x, _f_y, _f_s=10, **_f_kwargs):
        # Calculate the value
        _coef = np.corrcoef(_f_x, _f_y)[0][1]
        # Make the label
        _label = r'$\rho$ = ' + str(round(_coef, 2))

        # Add the label to the plot
        _ax = plt.gca()
        _ax.annotate(_label, xy=(0.2, 0.95 - (_f_s - 10.) / 10.), size=20, xycoords=_ax.transAxes, **_f_kwargs)

    # Create an instance of the PairGrid class.
    _grid = sns.PairGrid(data=df_in,
                         vars=vars_in,
                         **kwargs)

    # Map a scatter plot to the upper triangle
    _grid = _grid.map_upper(plt.scatter, alpha=alpha_in, color=color_in)
    # Map a corr coef
    _grid = _grid.map_upper(_f_corr)

    # Map a histogram to the diagonal

    # density = True might not be supported in older versions of seaborn / matplotlib
    _grid = _grid.map_diag(plt.hist, bins=30, color=color_in, alpha=alpha_in, edgecolor='k', density=True)

    # Map a density plot to the lower triangle
    _grid = _grid.map_lower(sns.kdeplot, cmap=cmap_in, alpha=alpha_in)

    # add legend
    _grid.add_legend()

    # show
    plt.show()


# quick x limits for plotting (cut off data not in 10%-90% quantile)
def q_plim(pd_series, q_min=.1, q_max=.9, offset_perc=.1, limit_min_max=False, offset=True):
    _lower_bound = floor_signif(pd_series.quantile(q=q_min))
    _upper_bound = ceil_signif(pd_series.quantile(q=q_max))

    if _upper_bound == _lower_bound:
        _upper_bound = pd_series.max()
        _lower_bound = pd_series.min()

    if limit_min_max:

        if _upper_bound > pd_series.max():
            _upper_bound = pd_series.max()
        if _lower_bound < pd_series.min():
            _lower_bound = pd_series.min()

    if offset:

        _offset = (_upper_bound - _lower_bound) * offset_perc

    else:

        _offset = 0

    return _lower_bound - _offset, _upper_bound + _offset


# leveled histogram
def level_histogram(df, cols, level, hue=None, level_colors=None, pattern=None, do_print=False,
                    figsize=None, scale=1, col_labels=None, level_labels=None, hue_labels=None,
                    distplot_title='Distplot all Levels', hspace=.6, return_fig_ax=False, distkws=None,
                    dist_kws=None):
    if pattern is None:
        pattern = rcParams['palette']
    if distkws is None:
        distkws = {}
    if dist_kws is None:
        dist_kws = {}
    _df = df.copy()

    _levels = _df[level].value_counts().reset_index()['index']

    if hue is not None:
        _df[hue] = _df[hue].astype('category')
        _hues = _df[hue].value_counts().reset_index()['index']

    _nrows = len(cols)
    _ncols = len(_levels) + 1

    if figsize is None:
        figsize = [16 * 2, _nrows * ((9 / 2) + hspace)] * scale

    fig, ax = plt.subplots(nrows=_nrows, ncols=_ncols, figsize=figsize)

    for _col_i in range(len(cols)):

        _col = cols[_col_i]

        if col_labels is not None:
            _col_label = col_labels[_col]
        else:
            _col_label = _col

        # apply xlim:

        _xlim = q_plim(df[_col])
        _df = df[(df[_col] >= _xlim[0]) & (df[_col] <= _xlim[1])]

        # adjust hues if applicable
        if hue_labels is not None:

            _df[hue] = _df[hue].replace(hue_labels)

            if isinstance(pattern, Mapping):

                for _key in hue_labels.keys():

                    if _key in pattern.keys():
                        pattern[hue_labels[_key]] = pattern.pop(_key)

        for _level_i, _level in enumerate(_levels):

            if isinstance(level_colors, Mapping):
                _level_color = level_colors[_level]
            elif is_list_like(level_colors):
                _level_color = level_colors[_level_i]
            else:
                _level_color = None

            if do_print:
                tprint(_col, _level)

            _df_level = _df[_df[level] == _level]

            # histogram
            # get axis
            _ax = get_subax(ax, _col_i, _level_i + 1)
            _ax_distplot = get_subax(ax, _col_i, 0, rows_prio=False)  # always plot to col 0 of current row

            if level_labels is not None:
                _level_label = level_labels[_level]
            else:
                _level_label = _level

            distplot(_df_level, _col, hue=hue, pattern=pattern, ax=_ax, **distkws)

            # noinspection PyTypeChecker
            _ax.set_xlim(_xlim)
            _ax.set_title(_level_label + ': ' + _col_label)

            # summary distplot
            try:
                sns.distplot(_df_level[_col].dropna(), hist=False, kde=True, label=_level_label, ax=_ax_distplot,
                             color=_level_color, **dist_kws)
            except ValueError:
                _ = ''  # do nothing

            _ax_distplot.set_title(distplot_title)
            # noinspection PyTypeChecker
            _ax_distplot.set_xlim(_xlim)
            _ax_distplot.set_xlabel(_col_label)
            _ax_distplot.legend()

    if do_print:
        tprint('create plot')

    fig.patch.set_facecolor('white')

    if return_fig_ax:

        return fig, ax

    else:

        plt.subplots_adjust(hspace=hspace)
        plt.show()


# leveled countplot
def level_countplot(data, level, hue, ncols=4, level_colors=None, hue_colors=None, do_print=False,
                    figsize=None, scale=1, palette=None, level_labels=None, hue_labels=None,
                    levelplot_title='Count per Level', hspace=.6,
                    return_fig_ax=False, subplots_kws=None, **kwargs):
    # default values
    if subplots_kws is None:
        subplots_kws = {}
    if palette is None:
        palette = rcParams['palette'] + []
    _row = None
    _col = None

    _levels = ['all'] + list(data[level].value_counts().reset_index()['index'])

    if hue is not None:
        _hues = sorted(data[hue].unique())

    _nrows = int(np.ceil(len(_levels) / ncols))

    if figsize is None:
        figsize = [16 * 2, _nrows * ((9 / 2) + hspace)] * scale

    fig, ax = plt.subplots(nrows=_nrows, ncols=ncols, figsize=figsize, **subplots_kws)

    _df = data.copy()
    _df['_dummy'] = 1

    # adjust hues if applicable
    if hue_labels is not None:

        _df[hue] = _df[hue].replace(hue_labels)

        if hue_colors is not None:

            for _key in list(hue_labels.keys()):

                if _key in list(hue_colors.keys()):
                    hue_colors[hue_labels[_key]] = hue_colors.pop(_key)

    for _level_i in range(len(_levels)):

        _col = _level_i % ncols
        _row = _level_i // ncols

        # get axis
        _ax = get_subax(ax, _row, _col, rows_prio=False)

        _level = _levels[_level_i]

        if level_colors is not None:
            _level_color = level_colors[_level]  # should be a dict
        else:
            _level_color = palette[_level_i]

        if level_labels is not None:
            _level_label = level_labels[_level]
        else:
            _level_label = _level

        if do_print:
            tprint(_col, _level)

        if _level == 'all':

            # first plot: counts per level
            countplot(data=_df, x=level, ax=_ax, **kwargs)
            _ax.set_title(levelplot_title)

        else:
            # subsequent plots: cols per hue

            _df_level = _df[_df[level] == _level]

            countplot(data=_df_level, x=hue, ax=_ax, **kwargs)
            _ax.set_title(_level_label)

    # hide remaining empty axis
    for __col in range(_col + 1, ncols, 1):
        ax[_row, __col].set_axis_off()

    if do_print:
        tprint('create plot')

    if return_fig_ax:

        return fig, ax

    else:

        plt.subplots_adjust(hspace=hspace)
        plt.show()


# returns all legends on a given axis
def get_legends(ax):
    return [c for c in ax.get_children() if isinstance(c, Legend)]


# a plot to compare four components of a dataframe
def four_comp_plot(data, x_1, y_1, x_2, y_2, hue_1=None, hue_2=None,
                   lim=None, return_fig_ax=False,
                   **kwargs):
    # you can pass the hues to use or if none are given the default ones (std,plus/minus) are used
    # you can pass xlim and y_lim or assume default (4 std)

    # four components, ie 2 x 2
    if lim is None:
        lim = {'x_1': 'default', 'x_2': 'default', 'y_1': 'default', 'y_2': 'default'}
    _nrows = 2
    _ncols = 2

    # init plot
    fig, ax = plt.subplots(ncols=_ncols, nrows=_nrows, figsize=(16, 9))

    # make a copy yo avoid inplace operations
    _df_plot = data.copy()

    _x_std = _df_plot[x_1].std()
    _y_std = _df_plot[y_1].std()

    # type 1: split by size in relation to std
    if hue_1 is None:
        _df_plot['std'] = np.where((np.abs(_df_plot[x_1]) <= 1 * _x_std) & (np.abs(_df_plot[y_1]) <= 1 * _y_std),
                                   '0_std', 'Null')
        _df_plot['std'] = np.where((np.abs(_df_plot[x_1]) > 1 * _x_std) | (np.abs(_df_plot[y_1]) > 1 * _y_std), '1_std',
                                   _df_plot['std'])
        _df_plot['std'] = np.where((np.abs(_df_plot[x_1]) > 2 * _x_std) | (np.abs(_df_plot[y_1]) > 2 * _y_std), '2_std',
                                   _df_plot['std'])
        _df_plot['std'] = np.where((np.abs(_df_plot[x_1]) > 3 * _x_std) | (np.abs(_df_plot[y_1]) > 3 * _y_std), '3_std',
                                   _df_plot['std'])
        _df_plot['std'] = _df_plot['std'].astype('category')

        hue_1 = 'std'

    # type 2: split by plus minus
    if hue_2 is None:
        _df_plot['plus_minus'] = np.where((_df_plot[x_1] <= 0) & (_df_plot[y_1] <= 0), '- -', 'Null')
        _df_plot['plus_minus'] = np.where((_df_plot[x_1] <= 0) & (_df_plot[y_1] > 0), '- +', _df_plot['plus_minus'])
        _df_plot['plus_minus'] = np.where((_df_plot[x_1] > 0) & (_df_plot[y_1] <= 0), '+ -', _df_plot['plus_minus'])
        _df_plot['plus_minus'] = np.where((_df_plot[x_1] > 0) & (_df_plot[y_1] > 0), '+ +', _df_plot['plus_minus'])
        _df_plot['plus_minus'] = _df_plot['plus_minus'].astype('category')

        hue_2 = 'plus_minus'

    _xs = [x_1, x_2]
    _ys = [y_1, y_2]
    _hues = [hue_1, hue_2]

    _xlims = [lim['x_1'], lim['x_2']]
    _ylims = [lim['y_1'], lim['y_2']]

    for _row in range(_nrows):

        for _col in range(_ncols):

            # init
            _ax = get_subax(ax, _row, _col)

            _x_name = _xs[_col]
            _y_name = _ys[_col]
            _hue = _hues[_row]

            _x = _df_plot[_x_name]
            _y = _df_plot[_y_name]

            # scatterplot
            _ax = sns.scatterplot(data=_df_plot, x=_x_name, y=_y_name, hue=_hue, marker='.', ax=_ax, **kwargs)

            # grid 0 line
            _ax.axvline(0, color='k', alpha=.5, linestyle=':')
            _ax.axhline(0, color='k', alpha=.5, linestyle=':')

            # title
            _ax.set_title('%s vs %s, hue: %s' % (_x_name, _y_name, _hue))

            # labels
            _ax.set_xlabel(_x_name)
            _ax.set_ylabel(_y_name)

            # set limits to be 4 std range
            if _xlims[_col] == 'default':

                _x_low = -_x.std() * 4
                if _x.min() > _x_low:
                    _x_low = _x.min()

                _x_high = _x.std() * 4
                if _x.max() < _x_high:
                    _x_high = _x.max()

                _ax.set_xlim([_x_low, _x_high])

            if _ylims[_col] == 'default':

                _y_low = -_y.std() * 4
                if _y.min() > _y_low:
                    _y_low = _y.min()

                _y_high = _y.std() * 4
                if _y.max() < _y_high:
                    _y_high = _y.max()

                _ax.set_ylim([_y_low, _y_high])

    if return_fig_ax:
        return fig, ax
    else:
        plt.tight_layout()
        plt.show()


# facet wrap like ggplot
def facet_wrap(func, data, facet, *args, col_wrap=4, width=4, height=9 / 2, catch_error=True,
               return_fig_ax=False, tight_layout=False, legend_out=False, sharex=False, sharey=False, show_xlabel=True,
               x_tick_rotation=None, y_tick_rotation=None, ax_title='set', order=None, suptitle=None,
               linebreak_x_kws=None, linebreak_y_kws=None, subplots_kws=None, subplots_adjust_kws=None, **kwargs):
    # facet can be one column name to use as facet OR a list of column names
    # subplots_kws,subplots_adjust_kws should be dictionaries

    # avoid inplace operations
    if linebreak_x_kws is None:
        linebreak_x_kws = {}
    if linebreak_y_kws is None:
        linebreak_y_kws = {}
    if subplots_kws is None:
        subplots_kws = {}
    if subplots_adjust_kws is None:
        subplots_adjust_kws = {}
    _df = data.copy()
    _facet = None
    _row = None
    _col = None

    # if it is a list of column names we will melt the df together
    if isinstance(facet, list):

        _type_list = True
        _facets = facet

    else:  # if not a list assume it is the name of the column that has the facet levels

        _type_list = False
        _facet = facet

        # get facets sorted by value counts
        if order is None:
            _facets = _df[_facet].value_counts().reset_index()['index']
        else:
            _facets = order + []

    # init a grid
    if len(_facets) > col_wrap:
        _ncols = col_wrap
        _nrows = int(np.ceil(len(_facets) / _ncols))
    else:
        _ncols = len(_facets)
        _nrows = 1

    fig, ax = plt.subplots(ncols=_ncols, nrows=_nrows, figsize=(width * _ncols, height * _nrows), **subplots_kws)
    _ax_list = ax_as_list(ax)

    _xlim_min = np.nan
    _xlim_max = np.nan
    _ylim_min = np.nan
    _ylim_max = np.nan

    # loop facets
    for _it in range(len(_facets)):

        _col = _it % _ncols
        _row = _it // _ncols

        _ax = _ax_list[_it]

        # get df facet
        _facet_i = _facets[_it]

        # for list set target to be in line with facet to ensure proper naming
        if _type_list:
            _df_facet = _df.copy()
            _args = [_facet_i] + list(args)
        else:
            _df_facet = _df[_df[_facet] == _facet_i]
            _args = args

        # apply function on target (try catch)
        if catch_error:
            try:
                func(*_args, data=_df_facet, ax=_ax, **kwargs)
            except Exception as _exc:
                warnings.warn('could not plot facet {} with exception {}, skipping. '
                              'For details use catch_error=False'.format(_exc, _facet_i))
                _ax.set_axis_off()
                continue
        else:
            func(*_args, data=_df_facet, ax=_ax, **kwargs)

        # set axis title to facet or hide it or do nothing (depending on preference)
        if ax_title == 'set':
            _ax.set_title(_facet_i)
        elif ax_title == 'hide':
            _ax.set_title('')

        # check for legend outside keyword
        if legend_out:
            legend_outside(_ax)

        # tick rotation
        if x_tick_rotation is not None:
            _ax.xaxis.set_tick_params(rotation=x_tick_rotation)
        if y_tick_rotation is not None:
            _ax.yaxis.set_tick_params(rotation=y_tick_rotation)

        # hide x label (if appropriate)
        if not show_xlabel:
            _ax.set_xlabel('')

    # hide unused axes
    for __col in range(_col + 1, _ncols):
        ax[_row, __col].set_axis_off()

    fig.patch.set_facecolor('white')

    # postprocessing
    if sharex or sharey or (len(linebreak_x_kws) > 0) or (len(linebreak_y_kws) > 0):

        # We need to draw the canvas, otherwise the labels won't be positioned and we won't have values yet.
        fig.canvas.draw()

        for _it in range(len(_facets)):

            _col = _it % _ncols
            _row = _it // _ncols

            # set x lim / x lim to be shared (if applicable)
            _ax = get_subax(ax, _row, _col, rows_prio=False)

            # add linebreaks
            if len(linebreak_x_kws) > 0:
                ax_tick_linebreaks(_ax, y=False, **linebreak_x_kws)
            if len(linebreak_y_kws) > 0:
                ax_tick_linebreaks(_ax, x=False, **linebreak_y_kws)

    share_xy(ax, x=sharex, y=sharey)

    if suptitle is not None:
        plt.suptitle(suptitle)
        if 'top' not in subplots_adjust_kws.keys():
            subplots_adjust_kws['top'] = .95
    if len(subplots_adjust_kws) > 0:
        plt.subplots_adjust(**subplots_adjust_kws)
    if tight_layout:
        plt.tight_layout()

    if return_fig_ax:
        return fig, ax
    else:
        plt.show()


# shorthand to get around the fact that ax can be a list or an array (for subplots that can be 1x1,1xn,nx1)
def get_subax(ax, row=None, col=None, rows_prio=True) -> Axes:
    # rows_prio decides if to use row or col in case of a 1xn / nx1 shape (false means cols get priority)

    if isinstance(ax, np.ndarray):
        _dims = len(ax.shape)
    else:
        _dims = 0

    if _dims == 0:
        _ax = ax
    elif _dims == 1:
        if rows_prio:
            _ax = ax[row]
        else:
            _ax = ax[col]
    else:
        _ax = ax[row, col]

    return _ax


def ax_as_list(ax):
    if isinstance(ax, np.ndarray):
        _dims = len(ax.shape)
    else:
        _dims = 0

    if _dims == 0:
        _ax_list = [ax]
    elif _dims == 1:
        _ax_list = list(ax)
    else:
        _ax_list = list(ax.flatten())

    return _ax_list


def ax_as_array(ax):

    if isinstance(ax, np.ndarray):
        if len(ax.shape) == 2:
            return ax
        else:
            return ax.reshape(-1, 1)
    else:
        return np.array([ax]).reshape(-1, 1)


# bubble plot
def bubbleplot(x, y, hue, s, text=None, text_as_label=False, color=None, data=None, s_factor=250, palette=None,
               hue_order=None, hue_color=None, x_range_factor=5, y_range_factor=5, show_std=False, grid=False, ax=None,
               legend_loc='right', text_kws=None):
    if palette is None:
        palette = rcParams['palette']
    if text_kws is None:
        text_kws = {}
    _df = data.copy().reset_index(drop=True)

    # print(_df)

    _df = _df[~((_df[x].isnull()) | (_df[y].isnull()) | (_df[s].isnull()))]

    if hue_order is not None:
        _df['_sort'] = _df[hue].apply(lambda _: hue_order.index(_))
        _df = _df.sort_values(by=['_sort'])

    _df = _df.reset_index(drop=True)

    _x = _df[x]
    _y = _df[y]
    _s = _df[s] * s_factor

    if text is not None:
        _text = _df[text]
    else:
        _text = pd.Series()

    # color logic
    if hue_color is not None:  # hue color takes precedence (should be a dict with hue levels as keys)

        _df['_color'] = _df[hue].apply(lambda _: hue_color[_])

    else:

        if color is None:

            if palette is None:
                _df['_color'] = palette[:_df.index.max() + 1]
            else:
                _df['_color'] = palette[:_df.index.max() + 1]

        else:

            _df['_color'] = _df[color]

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 10))

    # draw ellipse to mark 1 sigma area
    if show_std:

        _x_min = None
        _x_max = None
        _y_min = None
        _y_max = None

        for _index, _row in _df.iterrows():

            _ellipse = patches.Ellipse(xy=(_row[x], _row[y]), width=_row[x + '_std'] * 2, height=_row[y + '_std'] * 2,
                                       edgecolor=_row['_color'], fc='None', lw=2, ls=':')
            ax.add_patch(_ellipse)

            _x_min_i = _row[x] - _row[x + '_std'] * 1.05
            _x_max_i = _row[x] + _row[x + '_std'] * 1.05
            _y_min_i = _row[y] - _row[y + '_std'] * 1.05
            _y_max_i = _row[y] + _row[y + '_std'] * 1.05

            if _x_min is None:
                _x_min = _x_min_i
            elif _x_min_i < _x_min:
                _x_min = _x_min_i
            if _x_max is None:
                _x_max = _x_max_i
            elif _x_max_i > _x_max:
                _x_max = _x_max_i
            if _y_min is None:
                _y_min = _y_min_i
            elif _y_min_i < _y_min:
                _y_min = _y_min_i
            if _y_max is None:
                _y_max = _y_max_i
            elif _y_max_i > _y_max:
                _y_max = _y_max_i

    else:
        # scatter for bubbles
        ax.scatter(x=_x, y=_y, s=_s, label='__nolegend__', facecolor=_df['_color'], edgecolor='black', alpha=.75)

        _x_range = _x.max() - _x.min()
        _x_min = _x.min() - _x_range / x_range_factor
        _x_max = _x.max() + _x_range / x_range_factor

        _y_range = _y.max() - _y.min()
        _y_min = _y.min() - _y_range / y_range_factor
        _y_max = _y.max() + _y_range / y_range_factor

    # plot fake data for legend (a little hacky)
    if text_as_label:

        _xlim_before = ax.get_xlim()

        for _it in range(len(_x)):
            _label = _text[_it]
            # fake data
            ax.scatter(x=-9999, y=_y[_it], label=_label, facecolor=_df['_color'].loc[_it], s=200, edgecolor='black',
                       alpha=.75)

        ax.set_xlim(_xlim_before)

    if (text is not None) and (not text_as_label):
        for _it in range(len(_text)):

            _ = ''

            if (not np.isnan(_x.iloc[_it])) and (not np.isnan(_y.iloc[_it])):
                ax.text(x=_x.iloc[_it], y=_y.iloc[_it], s=_text.iloc[_it], horizontalalignment='center',
                        verticalalignment='center', **text_kws)

    # print(_x_min,_x_max)

    ax.set_xlim(_x_min, _x_max)
    ax.set_ylim(_y_min, _y_max)

    ax.set_xlabel(_x.name)
    ax.set_ylabel(_y.name)

    if text_as_label and (legend_loc in ['bottom', 'right']):
        legend_outside(ax, loc=legend_loc)
    else:
        ax.legend(loc=legend_loc)

    # ax.set_axis_off()

    # title
    ax.set_title(hue)
    if grid:
        ax.grid()

    return ax


def bubblecountplot(x, y, hue, data, agg_function='median', show_std=True, top_nr=None, n_quantiles=10,
                    other_name='other', dropna=True, float_format='.2f', text_end='', **kwargs):
    _df = data.copy()

    if dropna:
        _df = _df[~_df[hue].isnull()]

    if hue in _df.select_dtypes(include=np.number):

        _n = n_quantiles

        if top_nr is not None:
            if top_nr < n_quantiles:
                _n = top_nr

        _df[hue] = quantile_split(_df[hue], _n)

    if top_nr is not None:
        _df[hue] = top_n_coding(_df[hue], n=top_nr, other_name=other_name)

    # handle na
    _df[x] = _df[x].fillna(_df[x].dropna().agg(agg_function))
    _df[y] = _df[y].fillna(_df[y].dropna().agg(agg_function))

    # build agg dict
    _df['_count'] = 1
    _df = _df.groupby([hue]).agg({x: [agg_function, 'std'], y: [agg_function, 'std'], '_count': 'count'}).reset_index()
    if x != y:
        _columns = [hue, x, x + '_std', y, y + '_std', '_count']
    else:
        _columns = [hue, x, x + '_std', '_count']
    _df.columns = _columns
    _df['_perc'] = _df['_count'] / _df['_count'].sum() * 100
    _df['_count_text'] = _df.apply(lambda _: "{:,}".format(_['_count']), axis=1)
    _df['_perc_text'] = np.round(_df['_perc'], 2)
    _df['_perc_text'] = _df['_perc_text'].astype(str) + '%'

    if show_std:
        _df['_text'] = _df[hue].astype(str) + '(' + _df['_count_text'] + ')' + '\n' \
                       + 'x:' + _df[x].apply(lambda _: format(_, float_format)) + r'$\pm$' + _df[x + '_std'].apply(
            lambda _: format(_, float_format)) + '\n' \
                       + 'y:' + _df[y].apply(lambda _: format(_, float_format)) + r'$\pm$' + _df[y + '_std'].apply(
            lambda _: format(_, float_format))
    else:
        _df['_text'] = _df[hue].astype(str) + '\n' + _df['_count_text'] + '\n' + _df['_perc_text']

    _df['_text'] += text_end

    bubbleplot(x=x, y=y, hue=hue, s='_perc', text='_text', data=_df, show_std=show_std, **kwargs)


# plot rmsd
def rmsdplot(x, data, groups=None, hue=None, hue_order=None, cutoff=0, ax=None, figsize=(10, 10),
             color_as_balance=True, balance_cutoff=None, rmsd_as_alpha=False, sort_by_hue=False,
             line_break_kws=None, barh_kws=None, palette=None, **kwargs):
    if palette is None:
        palette = rcParams['palette']
    if line_break_kws is None:
        line_break_kws = {}
    if barh_kws is None:
        barh_kws = {}
    _data = data.copy()
    del data

    if hue is not None and hue_order is not None:
        _data = _data.query('{} in @hue_order'.format(hue))

    _df_rmsd = df_rmsd(x=x, df=_data, groups=groups, hue=hue, sort_by_hue=sort_by_hue, **kwargs)
    _df_rmsd = _df_rmsd[_df_rmsd['rmsd'] >= cutoff]

    if hue is not None:
        _df_rmsd_no_hue = df_rmsd(x=x, df=_data, groups=groups, include_rmsd=False, **kwargs)
    else:
        _df_rmsd_no_hue = pd.DataFrame()

    if isinstance(x, list):
        if hue is None:
            _df_rmsd['label'] = concat_cols(_df_rmsd, ['x', 'group'], sep=' X ')
        else:
            _df_rmsd['label'] = concat_cols(_df_rmsd, ['x', 'group', hue], sep=' X ')
    else:
        if hue is None:
            _df_rmsd['label'] = _df_rmsd['group']
        else:
            _df_rmsd['label'] = concat_cols(_df_rmsd, ['group', hue], sep=' X ')

    _df_rmsd['rmsd_scaled'] = _df_rmsd['rmsd'] / _df_rmsd['rmsd'].max()

    # get colors
    _rgba_colors = np.zeros((len(_df_rmsd), 4))
    _hues = []

    if hue is not None:

        if hue_order is not None:
            _hues = hue_order
        else:
            _hues = _df_rmsd[hue].cat.categories

        _df_rmsd['_color'] = _df_rmsd[hue].apply(lambda _l: palette[list(_hues).index(_l)])

        _rgba_colors[:, 0] = _df_rmsd['_color'].apply(lambda _l: Color(_l).red)
        _rgba_colors[:, 1] = _df_rmsd['_color'].apply(lambda _l: Color(_l).green)
        _rgba_colors[:, 2] = _df_rmsd['_color'].apply(lambda _l: Color(_l).blue)

    elif color_as_balance:

        if balance_cutoff is None:

            _rgba_colors[:, 0] = _df_rmsd['maxperc']  # for red the first column needs to be one
            _rgba_colors[:, 2] = 1 - _df_rmsd['maxperc']  # for blue the third column needs to be one

        else:

            _rgba_colors[:, 0] = np.where(_df_rmsd['maxperc'] >= balance_cutoff, 1, 0)
            _rgba_colors[:, 2] = np.where(_df_rmsd['maxperc'] < balance_cutoff, 1, 0)

    else:
        _rgba_colors[:, 2] = 1  # for blue the third column needs to be one

    # the fourth column needs to be alphas
    if rmsd_as_alpha:
        _rgba_colors[:, 3] = _df_rmsd['rmsd_scaled']
    else:
        _rgba_colors[:, 3] = 1

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    # make positions from labels

    if hue is not None:
        _pos_factor = .8
    else:
        _pos_factor = 1

    _df_rmsd['pos'] = _df_rmsd.index * _pos_factor

    if (hue is not None) and (not sort_by_hue):
        # iterate over rows and add to pos if label changes
        for _row in range(1, len(_df_rmsd)):
            if _df_rmsd['group'].iloc[_row] != _df_rmsd['group'].iloc[_row - 1]:
                _df_rmsd['pos'][_row:] = _df_rmsd['pos'][_row:] + _pos_factor

        # make a df of the average positions for each group
        _df_ticks = _df_rmsd.groupby('group').agg({'pos': 'mean'}).reset_index()  # 'maxperc':'max'
        _df_ticks = pd.merge(_df_ticks, _df_rmsd_no_hue[['group', 'maxperc']])  # get maxperc from global value
    else:
        _df_ticks = pd.DataFrame()

    ax.barh(_df_rmsd['pos'], _df_rmsd['rmsd'], color=_rgba_colors, **barh_kws)

    _y_colors = None

    if (hue is not None) and (not sort_by_hue):

        _y_pos = _df_ticks['pos']
        _y_lab = _df_ticks['group']
        # color
        if balance_cutoff is not None:
            _y_colors = np.where(_df_ticks['maxperc'] > balance_cutoff, sns.xkcd_rgb['red'], 'k')

    else:

        _y_pos = _df_rmsd['pos']

        if not is_list_like(x):
            _y_lab = _df_rmsd['group']
        elif not is_list_like(groups):
            _y_lab = _df_rmsd['x']
        else:
            _y_lab = concat_cols(_df_rmsd, ['x', 'group'], sep=' X ')

    # format labels
    if len(line_break_kws) > 0:
        _y_lab = _y_lab.apply(lambda _: insert_linebreak(_, **line_break_kws))

    ax.set_yticks(_y_pos)
    ax.set_yticklabels(_y_lab)

    if _y_colors is not None:
        for _y_tick, _color in zip(ax.get_yticklabels(), _y_colors):
            _y_tick.set_color(_color)

    if hue is None:
        _offset = _pos_factor
    else:
        _offset = _pos_factor * len(_hues)

    ax.set_ylim([_y_pos.min() - _offset, _y_pos.max() + _offset])

    ax.invert_yaxis()

    # create legend for hues
    if hue is not None:

        _patches = []
        for _hue, _color, _count in _df_rmsd[[hue, '_color', 'count']].drop_duplicates().values:
            _patches.append(patches.Patch(color=_color, label='{} (n={:,})'.format(_hue, _count)))
        ax.legend(handles=_patches)

    # check if standardized
    _x_label_suffix = ''

    if 'standardize' in kwargs.keys():
        if kwargs['standardize']:
            _x_label_suffix += ' [std]'

    if not is_list_like(x):
        ax.set_title('Root Mean Square Difference for {}'.format(x))
        ax.set_xlabel('RMSD: {}{}'.format(x, _x_label_suffix))
    elif not is_list_like(groups):
        ax.set_title('Root Mean Square Difference for {}'.format(groups))
        ax.set_xlabel('RMSD: {}{}'.format(groups, _x_label_suffix))
    else:
        ax.set_title('Root Mean Square Difference')

    if ax is None:
        plt.gcf().patch.set_facecolor('white')
        plt.show()
    else:
        return ax


# plot agg
def aggplot(x, data, group, hue=None, width=16, height=9 / 2,
            p_1_0=True, palette=None, sort_by_hue=False, return_fig_ax=False, agg=None, p=False,
            legend_loc='upper right', aggkws=None, subplots_kws=None, subplots_adjust_kws=None, **kwargs):
    # avoid inplace operations
    if palette is None:
        palette = rcParams['palette']
    if agg is None:
        agg = ['mean', 'median', 'std']
    if aggkws is None:
        aggkws = {}
    if subplots_kws is None:
        subplots_kws = {}
    if subplots_adjust_kws is None:
        subplots_adjust_kws = {'top': .95, 'hspace': .25, 'wspace': .35}
    _df = data.copy()
    _len = len(agg) + 1 + p

    _x = x
    _group = group

    # EITHER x OR group can be a list (hue cannot be a lists)
    if is_list_like(x) and is_list_like(group):

        warnings.warn('both x and group cannot be a list, setting group = {}'.format(group[0]))
        _x_is_list = True
        _group_is_list = False
        _group = group[0]
        _ncols = len(x)
        _nrows = _len

    elif isinstance(x, list):

        _x_is_list = True
        _group_is_list = False
        _group = group
        _ncols = len(x)
        _nrows = _len

    elif isinstance(group, list):

        _x_is_list = False
        _group_is_list = True
        _ncols = len(group)
        _nrows = _len

    else:

        _x_is_list = False
        _group_is_list = False
        _ncols = int(np.floor(_len / 2))
        _nrows = int(np.ceil(_len / 2))

    fig, ax = plt.subplots(figsize=(width * _ncols, height * _nrows), nrows=_nrows, ncols=_ncols, **subplots_kws)

    _it = -1

    for _col in range(_ncols):

        if _x_is_list:
            _x = x[_col]
        if _group_is_list:
            _group = group[_col]

        _df_agg = df_agg(x=_x, group=_group, hue=hue, df=_df, agg=agg, p=p, **aggkws)

        if hue is not None:
            if sort_by_hue:
                _sort_by = [hue, _group]
            else:
                _sort_by = [_group, hue]
            _df_agg = _df_agg.sort_values(by=_sort_by).reset_index(drop=True)
            _label = '_label'
            _df_agg[_label] = concat_cols(_df_agg, [_group, hue], sep='_').astype('category')
            _hues = _df_agg[hue].value_counts().reset_index()['index']
            # map colors to hues
            _df_agg['_color'] = _df_agg[hue].apply(lambda _l: palette[list(_hues).index(_l)])
            # inser rows of nan between groups (for white space)

        else:
            _label = _group

        for _row in range(_nrows):

            _it += 1

            if _x_is_list or _group_is_list:
                _index = _row
            else:
                _index = _it

            _ax = get_subax(ax, _row, _col)

            if _index >= _len:
                _ax.set_axis_off()
                continue

            _agg = list(_df_agg)[1:][_index]

            # one color per graph (if no hue)
            if hue is None:
                _df_agg['_color'] = palette[_index]

            # handle hue grouping
            if hue is not None:
                _pos_factor = .8
            else:
                _pos_factor = 1

            _df_agg['pos'] = _df_agg.index

            if (hue is not None) and (not sort_by_hue):
                # iterate over rows and add to pos if label changes
                for _row_2 in range(1, len(_df_agg)):
                    if _df_agg[_group].iloc[_row_2] != _df_agg[_group].iloc[_row_2 - 1]:
                        _df_agg['pos'][_row_2:] = _df_agg['pos'][_row_2:] + _pos_factor

                # make a df of the average positions for each group
                _df_ticks = _df_agg.groupby(_group).agg({'pos': 'mean'}).reset_index()
            else:
                _df_ticks = pd.DataFrame()

            _ax.barh('pos', _agg, color='_color', label=_agg, data=_df_agg, **kwargs)

            if (hue is not None) and (not sort_by_hue):
                _ax.set_yticks(_df_ticks['pos'])
                _ax.set_yticklabels(_df_ticks[_group])
            else:
                _ax.set_yticks(_df_agg['pos'])
                _ax.set_yticklabels(_df_agg[_group])

            _ax.invert_yaxis()
            _ax.set_xlabel(_x + '_' + _agg)
            _ax.set_ylabel(_group)

            # create legend for hues
            if hue is not None:
                _patches = []
                for _hue, _color in _df_agg[[hue, '_color']].drop_duplicates().values:
                    _patches.append(patches.Patch(color=_color, label=_hue))

                _ax.legend(handles=_patches)
            else:
                _ax.legend(loc=legend_loc)

            # range of p is between 0 and 1
            if _agg == 'p' and p_1_0:
                # noinspection PyTypeChecker
                _ax.set_xlim([0, 1])

    if _x_is_list:
        _x_title = ','.join(x)
    else:
        _x_title = _x

    if _group_is_list:
        _group_title = ','.join(group)
    else:
        _group_title = _group

    _title = _x_title + ' by ' + _group_title
    if hue is not None:
        _title = _title + ' per ' + hue

    plt.suptitle(_title, size=16)
    plt.subplots_adjust(**subplots_adjust_kws)

    if return_fig_ax:
        return fig, ax
    else:
        plt.show()


def aggplot2d(x, y, data, aggfunc='mean', ax=None, x_int=None, time_int=None,
              figsize=plt.rcParams['figure.figsize'], color=rcParams['palette'][0], as_abs=False):
    # time int should be something like '<M8[D]'
    # D can be any datetime unit from numpy https://docs.scipy.org/doc/numpy-1.13.0/reference/arrays.datetime.html

    # consts

    _y_agg = '{}_{}'.format(y, aggfunc)
    _y_std = '{}_std'.format(y)

    # preprocessing

    _df = data.copy()

    if as_abs:
        _df[y] = np.abs(_df[y])
    if x_int is not None:
        _df[x] = np.round(_df[x] / x_int) * x_int
    if time_int is not None:
        _df[x] = _df[x].astype('<M8[{}]'.format(time_int))

    # agg

    _df = _df.groupby([x]).agg({y: [aggfunc, 'std']}).set_axis([_y_agg, _y_std], axis=1, inplace=False).reset_index()

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
        _show = True
    else:
        _show = False

    ax.plot(_df[x], _df[_y_agg], color=color, label=_y_agg)
    ax.fill_between(_df[x], _df[_y_agg] + _df[_y_std], _df[_y_agg] - _df[_y_std], color='xkcd:cyan', label=_y_std)
    # ax.fill_between(_df[x],_df[_y_agg]-_df[_y_std],color=color,label='__nolegend__')
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.legend()

    if _show:
        plt.show()
    else:
        return ax


# a wrapper for use with facet wrap
def aggplot2dy(y, x, **kwargs):
    return aggplot2d(x=x, y=y, **kwargs)


def insert_linebreak(s, pos=None, frac=None, max_breaks=None):
    _s = s + ''

    if pos is not None:
        _pos = pos
        _frac = int(np.ceil(len(_s) / _pos))
    elif frac is not None:
        _pos = int(np.ceil(len(_s) / frac))
        _frac = frac
    else:
        _pos = None
        _frac = None

    _pos_i = 0

    if max_breaks is not None:
        _max = np.min([max_breaks, _frac - 1])
    else:
        _max = _frac - 1

    for _it in range(_max):

        _pos_i += _pos
        if _it > 0:
            _pos_i += 1  # needed because of from 0 indexing
        _s = _s[:_pos_i] + '\n' + _s[_pos_i:]

    # remove trailing newlines
    if _s[-1:] == '\n':
        _s = _s[:-1]

    return _s


def ax_tick_linebreaks(ax=None, x=True, y=True, **kwargs):
    if ax is None:
        ax = plt.gca()

    if x:
        ax.set_xticklabels([insert_linebreak(_item.get_text(), **kwargs) for _item in ax.get_xticklabels()])
    if y:
        ax.set_yticklabels([insert_linebreak(_item.get_text(), **kwargs) for _item in ax.get_yticklabels()])


def annotate_barplot(ax=None, x=None, y=None, ci=True, ci_newline=True, adj_ylim=.05, nr_format=',.2f', ha='center',
                     va='center', offset=plt.rcParams['font.size'], **kwargs):
    logging.getLogger().setLevel(logging.CRITICAL)

    if ax is None:
        ax = plt.gca()

    _adj_plus = False
    _adj_minus = False

    if ci_newline:
        _ci_sep = '\n'
        _offset = offset + 5
    else:
        _ci_sep = ''
        _offset = offset

    for _it, _patch in enumerate(ax.patches):

        try:

            if x is None:
                _x = _patch.get_x() + _patch.get_width() / 2.
            elif is_list_like(x):
                _x = x[_it]
            else:
                _x = x

            if y is None:
                _y = _patch.get_height()
            elif is_list_like(y):
                _y = y[_it]
            else:
                _y = y

            _val = _patch.get_height()

            if _val > 0:
                _adj_plus = True
            if _val < 0:
                _adj_minus = True

            if np.isnan(_val):
                continue

            _val_text = format(_val, nr_format)

            _annotate = r'${}$'.format(_val_text)

            # TODO: HANDLE CAPS

            if ci and ax.lines.__len__() > _it:
                _line = ax.lines[_it]

                _line_y = _line.get_xydata()[:, 1]
                _ci = (_line_y[1] - _line_y[0]) / 2

                if not np.isnan(_ci):
                    _ci_text = format(_ci, nr_format)
                    _annotate = r'${}$'.format(_val_text) + _ci_sep + r'$\pm{}$'.format(_ci_text)

            ax.annotate(_annotate, (_x, _y), ha=ha, va=va, xytext=(0, np.sign(_val) * _offset),
                        textcoords='offset points', **kwargs)

        except Exception as exc:
            print(exc)

    if adj_ylim:

        _ylim = list(ax.get_ylim())
        _y_adj = (_ylim[1] - _ylim[0]) * adj_ylim
        if _adj_minus:
            _ylim[0] = _ylim[0] - _y_adj
        if _adj_plus:
            _ylim[1] = _ylim[1] + _y_adj
        ax.set_ylim(_ylim)

    logging.getLogger().setLevel(logging.DEBUG)

    return ax


# animate a plot (wrapper for FuncAnimation to be used with pandas dfs)
def animplot(data=None, x='x', y='y', t='t', lines=None, max_interval=None, interval=200, html=True, title=True,
             title_prefix='', t_format=None,
             fig=None, ax=None, figsize=plt.rcParams['figure.figsize'], color=None, label=None, legend=False, legend_out=False,
             legend_kws=None, xlim=None, y_lim=None, ax_facecolor=None, grid=False,
             vline=None, **kwargs):
    # example for lines (a list of dicts)
    # lines = [{'line':line,'data':data,'x':'x','y':'y','t':'t'}]

    if legend_kws is None:
        legend_kws = {}
    _args = {'data': data, 'x': x, 'y': y, 't': t}

    # init fig,ax
    if fig is None:
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = plt.gcf()
    else:
        if ax is None:
            ax = plt.gca()

    _ax_list = ax_as_list(ax)

    # init lines
    if lines is None:

        _ax = _ax_list[0]

        lines = []

        _len = 1
        if is_list_like(x):
            _len = np.max([_len, len(x)])
        if is_list_like(y):
            _len = np.max([_len, len(y)])

        for _it in range(_len):

            if is_list_like(x):
                _x = x[_it]
            else:
                _x = x

            if is_list_like(y):
                _y = y[_it]
            else:
                _y = y

            if is_list_like(vline):
                _vline = vline[_it]
            else:
                _vline = vline

            if isinstance(color, Mapping):
                if _y in color.keys():
                    _color = color[_y]
                else:
                    _color = None
            elif is_list_like(color):
                _color = color[_it]
            else:
                _color = color

            _kwargs = deepcopy(kwargs)
            _kwargs_keys = list(_kwargs.keys())

            # defaults
            if len(list_intersection(['markerfacecolor', 'mfc'], _kwargs_keys)) == 0:
                _kwargs['markerfacecolor'] = _color
            if len(list_intersection(['markeredgecolor', 'mec'], _kwargs_keys)) == 0:
                _kwargs['markeredgecolor'] = _color
                if len(list_intersection(['markeredgewidth', 'mew'], _kwargs_keys)) == 0:
                    _kwargs['markeredgewidth'] = 1

            if label is None:
                _label = _y
            elif isinstance(label, Mapping):
                _label = label[_y]
            elif is_list_like(label):
                _label = label[_it]
            else:
                _label = label

            lines += [{
                'line': _ax.plot([], [], label=_label, color=_color, **_kwargs)[0],
                'ax': _ax,
                'data': data,
                'x': _x,
                'y': _y,
                't': t,
                'vline': _vline,
                'title': title,
                'title_prefix': title_prefix,
            }]

        _ts = pd.Series(data[t].unique()).sort_values()

    else:

        _ts = pd.Series()

        for _line in lines:

            _keys = list(_line.keys())

            # default: label = y
            if 'label' not in _keys:
                if 'y' in _keys:
                    _line['label'] = _line['y']
                elif y is not None:
                    _line['label'] = y

                # update keys
                _keys = list(_line.keys())

            # get kws
            _line_kws = {}
            _line_kw_keys = [_ for _ in _keys if _ not in ['ax', 'line', 'ts', 'data', 'x', 'y', 't']]
            _kw_keys = [_ for _ in list(kwargs.keys()) if _ not in _line_kw_keys]

            for _key in _line_kw_keys:
                _line_kws[_key] = _line[_key]
            for _kw_key in _kw_keys:
                _line_kws[_kw_key] = kwargs[_kw_key]

            if 'ax' not in _keys:
                _line['ax'] = _ax_list[0]
            if 'line' not in _keys:
                _line['line'] = _line['ax'].plot([], [], **_line_kws)[0],
            if is_list_like(_line['line']):
                _line['line'] = _line['line'][0]

            for _arg in list(_args.keys()):
                if _arg not in _keys:
                    _line[_arg] = _args[_arg]

            _line['ts'] = _line['data'][_line['t']].drop_duplicates().sort_values().reset_index(drop=True)

            _ts = _ts.append(_line['ts']).drop_duplicates().sort_values().reset_index(drop=True)

    # get max interval
    if max_interval is not None:
        if max_interval < _ts.shape[0]:
            _max_interval = max_interval
        else:
            _max_interval = _ts.shape[0]
    else:
        _max_interval = _ts.shape[0]

    # unchanging stuff goes here
    def init():

        for __ax in _ax_list:

            _xy_lim_set = False
            _x_min = None
            _x_max = None
            _y_min = None
            _y_max = None
            _legend = legend

            for __line in lines:

                # -- xy lims --

                if __ax == __line['ax']:

                    if not _xy_lim_set:

                        # init with limits of first line

                        _x_min = __line['data'][__line['x']].min()
                        _x_max = __line['data'][__line['x']].max()
                        _y_min = __line['data'][__line['y']].min()
                        _y_max = __line['data'][__line['y']].max()

                        _xy_lim_set = True

                    else:

                        # compare with x y lims of other lines

                        if __line['data'][__line['x']].min() < _x_min:
                            _x_min = __line['data'][__line['x']].min()
                        if __line['data'][__line['y']].min() < _y_min:
                            _y_min = __line['data'][__line['y']].min()
                        if __line['data'][__line['x']].max() > _x_max:
                            _x_max = __line['data'][__line['x']].max()
                        if __line['data'][__line['y']].max() > _y_max:
                            _y_max = __line['data'][__line['y']].max()

                    # -- legend --
                    if 'legend' in list(__line.keys()):
                        _legend = __line['legend']
                    if _legend:
                        if legend_out:
                            legend_outside(__ax, width=.995)
                        else:
                            __ax.legend(**legend_kws)

                    # -- vlines --
                    if 'vline' in __line.keys():
                        _vline_i = __line['vline']
                        if _vline_i is not None:
                            if not is_list_like(_vline_i):
                                _vline_i = [_vline_i]
                            for _vline_j in _vline_i:
                                __ax.axvline(_vline_j, color='k', linestyle=':')

            # -- lims --
            if xlim is not None:
                if xlim:
                    __ax.set_xlim(xlim)
            else:
                __ax.set_xlim([_x_min, _x_max])

            if y_lim is not None:
                if y_lim:
                    __ax.set_ylim(y_lim)
            else:
                __ax.set_ylim([_y_min, _y_max])

            # -- grid --
            if grid:
                __ax.grid()

            # -- ax facecolor --
            if isinstance(ax_facecolor, str):
                __ax.set_facecolor(ax_facecolor)

        return ()

    def animate(_i):

        _t = _ts[_i]

        for _line_i in lines:

            _line_keys_i = list(_line_i.keys())

            _data = _line_i['data'].copy()
            _data = _data[_data[_line_i['t']] == _t]

            _line_i['line'].set_data(_data[_line_i['x']], _data[_line_i['y']])

            if 'ax' in _line_keys_i:
                _ax_i = _line_i['ax']
            else:
                _ax_i = plt.gca()

            # -- title --
            _title = title
            _title_prefix = title_prefix

            if 'title' in list(_line_i.keys()):
                _title = _line_i['title']
            if 'title_prefix' in list(_line_i.keys()):
                _title_prefix = _line_i['title_prefix']

            if t_format is not None:
                _t_str = pd.to_datetime(_t).strftime(t_format)
            else:
                _t_str = _t

            if _title:
                _ax_i.set_title('{}{}'.format(_title_prefix, _t_str))

            # -- facecolor --
            if isinstance(ax_facecolor, Mapping):

                for _key_i in list(ax_facecolor.keys()):

                    _ax_facecolor = ax_facecolor[_key_i]
                    if (_key_i is None) or (_key_i > _t):
                        _ax_i.set_facecolor(_ax_facecolor)

        return ()

    for _line in lines:

        _line_keys = list(_line.keys())

        if 'ax' in _line_keys:
            _ax = _line['ax']
        else:
            _ax = plt.gca()

        _ax.set_xlim(_line['data'][_line['x']].min(), _line['data'][_line['x']].max())
        _ax.set_ylim(_line['data'][_line['y']].min(), _line['data'][_line['y']].max())

    _anim = FuncAnimation(fig, animate, init_func=init, frames=_max_interval, interval=interval, blit=True)

    plt.close('all')

    if html:
        return HTML(_anim.to_html5_video())
    else:
        return _anim


def legend_outside(ax=None, width=.85, loc='right', legend_space=.1, offset_x=0, offset_y=0, **kwargs):
    # -- init
    if loc not in ['bottom', 'right']:
        warnings.warn('legend_outside: legend loc not recognized')
        ax.legend(loc=loc, **kwargs)
        return None

    _loc = {'bottom': 'upper center', 'right': 'center left'}[loc]
    _bbox_to_anchor = {'bottom': (0.5 + offset_x, - .15 + offset_y), 'right': (1, 0.5)}[loc]

    if ax is None:
        ax = plt.gca()

    for _ax in ax_as_list(ax):

        # -- shrink box
        _box = _ax.get_position()
        _pos = {
            'bottom': [_box.x0, _box.y0, _box.width, _box.height * (1 - legend_space)],
            # 'bottom':[_box.x0, _box.y0 + _box.height * legend_space,_box.width, _box.height * (1-legend_space)],
            'right': [_box.x0, _box.y0, _box.width * width, _box.height]
        }[loc]
        _ax.set_position(_pos)

        # -- legend
        logging.getLogger().setLevel(logging.CRITICAL)
        _, _labels = _ax.get_legend_handles_labels()
        if len(_labels) > 0:
            _ax.legend(loc=_loc, bbox_to_anchor=_bbox_to_anchor, **kwargs)
        logging.getLogger().setLevel(logging.DEBUG)


def ax_set_x_sym(ax):
    _max = np.max(np.abs(np.array(ax.get_xlim())))
    ax.set_xlim([-_max, max])


def ax_set_y_sym(ax):
    _max = np.max(np.abs(np.array(ax.get_ylim())))
    ax.set_ylim([-_max, _max])


# uses patch to create a custom legend
def custom_legend(colors, labels, do_show=True):
    _handles = []

    for _color, _label in zip(colors, labels):
        _handles.append(patches.Patch(color=_color, label=_label))

    if do_show:
        plt.legend(handles=_handles)
    else:
        return _handles


def lcurveplot(train, test, labels=None, legend='upper right', ax=None, figsize=plt.rcParams['figure.figsize']):
    if labels is None:
        if 'name' in dir(train):
            _label_train = train.name
        else:
            _label_train = 'train'
        if 'name' in dir(test):
            _label_test = test.name
        else:
            _label_test = 'test'
    elif isinstance(labels, Mapping):
        _label_train = labels['train']
        _label_test = labels['test']
    elif is_list_like(labels):
        _label_train = labels[0]
        _label_test = labels[1]
    else:
        _label_train = labels
        _label_test = labels

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    ax.plot(train, color='xkcd:blue', label=_label_train)
    ax.plot(test, color='xkcd:red', label=_label_test)
    ax.plot(lfit(test), color='xkcd:red', ls='--', alpha=.75, label=_label_test + '_lfit')
    ax.axhline(np.min(test), color='xkcd:red', ls=':', alpha=.5)
    ax.axvline(np.argmin(test), color='xkcd:red', ls=':', alpha=.5)

    if legend:
        if isinstance(legend, str):
            _loc = legend
        else:
            _loc = None
        ax.legend(loc=_loc)

    return ax


def dic_to_lcurveplot(dic, width=16, height=9 / 2, **kwargs):
    if 'curves' not in dic.keys():
        warnings.warn('key curves not found, stopping')
        return None

    _targets = list(dic['curves'].keys())
    _nrows = len(_targets)

    _, ax = plt.subplots(nrows=_nrows, figsize=(width, height * _nrows))
    _ax_list = ax_as_list(ax)

    for _it, _target in enumerate(_targets):
        _ax = _ax_list[_it]
        lcurveplot(dic['curves'][_target]['train'], dic['curves'][_target]['test'],
                   labels=['{}_train'.format(_target), '{}_test'.format(_target)], ax=_ax, **kwargs)

    plt.show()


# re implementation of stemplot because customization sucks
def stemplot(x, y, data=None, ax=None, figsize=plt.rcParams['figure.figsize'], color=rcParams['palette'][0], baseline=0,
             kwline=None, **kwargs):
    if kwline is None:
        kwline = {}
    if data is None:

        if 'name' in dir(x):
            _x = x.name
        else:
            _x = 'x'

        if 'name' in dir(y):
            _y = y.name
        else:
            _y = 'x'

        _data = pd.DataFrame({_x: x, _y: y})

    else:

        _x = x
        _y = y
        _data = data.copy()

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    # baseline
    ax.axhline(baseline, color='k', ls='--', alpha=.5)

    # iterate over data so you can draw the lines
    for _it, _row in _data.iterrows():
        ax.plot([_row[_x], _row[_x]], [baseline, _row[_y]], color=color, label='__nolegend__', **kwline)

    # scatterplot for markers
    ax.scatter(x=_x, y=_y, data=_data, facecolor=color, **kwargs)

    return ax


def from_to_plot(data: pd.DataFrame, x_from='x_from', x_to='x_to', y_from=0, y_to=1, palette=None, label=None,
                 legend=True, legend_loc=None, ax=None, figsize=plt.rcParams['figure.figsize'], **kwargs):
    # defaults
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    if palette is None:
        palette = rcParams['palette']

    _labels = []

    for _, _row in data.itertuples():

        _label = '__nolabel__'

        _name = None

        if label is not None:

            _name = _row[label]

            if _name not in _labels:
                _label = _name + ''
                _labels.append(_label)

        if isinstance(palette, Mapping):
            _color = palette[_name]
        elif is_list_like(palette):
            _color = palette[_labels.index(_name)]
        else:
            _color = palette

        ax.fill_betweenx([y_from, y_to], _row[x_from], _row[x_to], label=_label, color=_color, **kwargs)

    if legend and label:
        ax.legend(loc=legend_loc)

    return ax


def vlineplot(data, palette=None, label=None, legend=True, legend_loc=None, ax=None,
              figsize=plt.rcParams['figure.figsize'], **kwargs):
    # defaults
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    if palette is None:
        palette = rcParams['palette']

    _labels = []

    _name = None

    for _, _row in data.iterrows():

        _label = '__nolabel__'

        if label is not None:

            _name = _row[label]

            if _name not in _labels:
                _label = _name + ''
                _labels.append(_label)

        if isinstance(palette, Mapping):
            _color = palette[_name]
        elif is_list_like(palette):
            _color = palette[_labels.index(_name)]
        else:
            _color = palette

        ax.axvline(_row['x'], label=_label, color=_color, **kwargs)

    if legend and label:
        ax.legend(loc=legend_loc)

    return ax


def show_ax_ticklabels(ax, x=None, y=None):
    _ax_list = ax_as_list(ax)

    for _ax in _ax_list:

        if x is not None:
            plt.setp(_ax.get_xticklabels(), visible=x)
        if y is not None:
            plt.setp(_ax.get_yticklabels(), visible=y)


def get_twin(ax):
    for _other_ax in ax.figure.axes:
        if _other_ax is ax:
            continue
        if _other_ax.bbox.bounds == ax.bbox.bounds:
            return _other_ax
    return False


def get_axlim(ax, xy=None):
    if xy == 'x':
        return ax.get_xlim()
    elif xy == 'y':
        return ax.get_ylim()
    else:
        return {'x': ax.get_xlim(), 'y': ax.get_ylim()}


def set_axlim(ax, lim, xy=None):
    if xy == 'x':
        ax.set_xlim(lim)
    elif xy == 'y':
        ax.set_ylim(lim)
    else:
        if isinstance(lim, Mapping):
            ax.set_xlim(lim['x'])
            ax.set_xlim(lim['y'])
        else:
            raise ValueError('Speficy xy parameter or pass a dictionary')


def share_xy(ax, x=True, y=True, mode='all', adj_twin_ax=True):
    _xys = []
    if x:
        _xys.append('x')
    if y:
        _xys.append('y')

    if isinstance(ax, np.ndarray):
        _dims = len(ax.shape)
    else:
        _dims = 0

    # slice for mode row / col (only applicable if shape==2)
    _ax_lists = []

    if (_dims <= 1) or (mode == 'all'):
        _ax_lists += [ax_as_list(ax)]
    elif mode == 'row':
        for _row in range(ax.shape[0]):
            _ax_lists += [ax_as_list(ax[_row, :])]
    elif mode == 'col':
        for _col in range(ax.shape[1]):
            _ax_lists += [ax_as_list(ax[:, _col])]

    # we can have different subsets (by row or col) that share x / y min
    for _ax_list in _ax_lists:

        # init as None
        _xy_min = {'x': None, 'y': None}
        _xy_max = {'x': None, 'y': None}

        # get min max
        for _ax in _ax_list:

            _lims = get_axlim(_ax)

            for _xy in _xys:

                _xy_min_i = _lims[_xy][0]
                _xy_max_i = _lims[_xy][1]

                if _xy_min[_xy] is None:
                    _xy_min[_xy] = _xy_min_i
                elif _xy_min[_xy] > _xy_min_i:
                    _xy_min[_xy] = _xy_min_i

                if _xy_max[_xy] is None:
                    _xy_max[_xy] = _xy_max_i
                elif _xy_max[_xy] < _xy_max_i:
                    _xy_max[_xy] = _xy_max_i

        # set min max
        for _ax in _ax_list:

            if adj_twin_ax:
                _ax2 = get_twin(_ax)
            else:
                _ax2 = False

            # collect xy funcs
            for _xy in _xys:

                # save old lim
                _old_lim = list(get_axlim(_ax, xy=_xy))
                # set new lim
                _new_lim = [_xy_min[_xy], _xy_max[_xy]]
                set_axlim(_ax, lim=_new_lim, xy=_xy)

                # adjust twin axis
                if _ax2:
                    _old_lim_2 = list(get_axlim(_ax2, xy=_xy))
                    _new_lim_2 = [0 if _old == 0 else _new / _old * _old2 for _new, _old, _old2 in
                                  zip(_new_lim, _old_lim, _old_lim_2)]
                    set_axlim(_ax2, lim=_new_lim_2, xy=_xy)


def share_legend(ax, keep_i=None):

    _ax_list = ax_as_list(ax)

    if keep_i is None:
        keep_i = len(_ax_list) // 2

    for _it, _ax in enumerate(_ax_list):

        _it += 1
        _legend = _ax.get_legend()
        if _it != keep_i and (_legend is not None):
            _legend.remove()


def replace_xticklabels(ax, mapping):
    _new_labels = []

    for _it, _label in enumerate(list(ax.get_xticklabels())):

        _text = _label.get_text()

        if isinstance(mapping, Mapping):
            if _text in mapping.keys():
                _new_label = mapping[_text]
            else:
                _new_label = _text
        else:
            _new_label = mapping[_it]

        _new_labels.append(_new_label)

    ax.set_xticklabels(_new_labels)


def replace_yticklabels(ax, mapping):
    _new_labels = []

    for _it, _label in enumerate(list(ax.get_yticklabels())):

        _text = _label.get_text()

        if isinstance(mapping, Mapping):
            if _text in mapping.keys():
                _new_label = mapping[_text]
            else:
                _new_label = _text
        else:
            _new_label = mapping[_it]

        _new_labels.append(_new_label)

    ax.set_yticklabels(_new_labels)


def kdeplot(x, data=None, *args, hue=None, hue_order=None, bins=40, adj_x_range=False, baseline=0, highlight_peaks=True,
            show_kde=True, show_hist=True, show_area=False, area_center='mean', ha='center', va='center',
            legend_loc='upper right', palette=None, text_offset=15, nr_format=',.2f',
            figsize=plt.rcParams['figure.figsize'], kwline=None, perc=False, facecolor=None, sigma_color='xkcd:blue',
            sigma_2_color='xkcd:cyan', kde_color='black', edgecolor='black', alpha=.5, ax=None, ax2=None, kwhist=None,
            **kwargs):
    # -- init
    if palette is None:
        palette = rcParams['palette']
    if kwline is None:
        kwline = {}
    if kwhist is None:
        kwhist = {}
    if data is not None:
        _df = data.copy()
        del data
        _x_name = x
    else:
        if 'name' in dir(x):
            _x_name = x.name
        else:
            _x_name = 'x'

        _df = pd.DataFrame({_x_name: x})

    _df = _df.dropna(subset=[_x_name])

    if hue is None:
        hue = '_dummy'
        _df[hue] = 1
    if hue_order is None:
        hue_order = sorted(_df[hue].unique())

    _x = _df[_x_name]

    if facecolor is None:
        if show_area:
            facecolor = 'None'
        else:
            facecolor = 'xkcd:cyan'

    if show_kde and show_area:
        _label_hist = '__nolabel__'
    else:
        _label_hist = _x_name

    # default
    if adj_x_range and isinstance(adj_x_range, bool):
        adj_x_range = 2

    # -- get kde
    _it = -1
    _twinx = False

    for _hue in hue_order:

        _it += 1
        _df_hue = _df.query('{}==@_hue'.format(hue))

        _df_kde, _df_kde_ex = kde(x=x, df=_df_hue, *args, **kwargs)

        if isinstance(palette, Mapping):
            _color = palette[_hue]
        elif is_list_like(palette):
            _color = palette[_it]
        else:
            _color = palette

        if hue == '_dummy':
            _kde_color = kde_color
            _edgecolor = edgecolor
            _facecolor = facecolor
        else:
            _kde_color = _color
            _edgecolor = _color
            _facecolor = 'None'
            _df_kde['value'] = _df_kde['value'] / _df_kde['value'].max()
            _df_kde_ex['value'] = _df_kde_ex['value'] / _df_kde['value'].max()

        if adj_x_range:
            _x_min = _df_kde_ex['range_min'].min()
            _x_max = _df_kde_ex['range_max'].max()

            _x_step = (_x_max - _x_min) / bins
            _x_range_min = _x_min - _x_step * adj_x_range * bins
            _x_range_max = _x_max + _x_step * adj_x_range * bins

            _df_hue = _df_hue.query('{}>=@_x_range_min & {}<=@_x_range_max'.format(_x_name, _x_name))
            _df_kde = _df_kde.query('{}>=@_x_range_min & {}<=@_x_range_max'.format(_x_name, _x_name))

        # -- plot

        if ax is None:
            _, ax = plt.subplots(figsize=figsize)

        # hist
        if show_hist:
            ax.hist(_df_hue[_x_name], bins, density=perc, facecolor=_facecolor, edgecolor=_edgecolor,
                    label=_label_hist, **kwhist)
            _twinx = True
        else:
            _twinx = False

        if _twinx and (ax2 is None):
            ax2 = ax.twinx()
        else:
            ax2 = ax

        _kde_label = '{} ; '.format(_x_name) + r'${:,.2f}\pm{:,.2f}$'.format(_df[_x_name].mean(), _df[_x_name].std())

        # kde
        ax2.plot(_df_kde[_x_name], _df_kde['value'], ls='--', label=_kde_label, color=_kde_color, **kwargs)

        _ylim = list(ax2.get_ylim())
        _ylim[0] = 0
        _ylim[1] = _ylim[1] * (100 + text_offset) / 100.
        ax2.set_ylim(_ylim)

        # area
        if show_area:

            # get max
            if area_center == 'max':
                _area_center = _df_kde[_df_kde['value'] == _df_kde['value'].max()].index[0]
            else:
                if area_center == 'mean':
                    _ref = _df_hue[_x_name].mean()
                else:
                    _ref = area_center

                _df_area = _df_kde.copy()
                _df_area['diff'] = (_df_area[_x_name] - area_center).abs()
                _df_area = _df_area.sort_values(by='diff', ascending=True)
                _area_center = _df_area.index[0]

            _sigma = None
            _2_sigma = None

            for _it in range(1, _df_kde.shape[0]):

                _perc_data = \
                    _df_kde[np.max([0, _area_center - _it]):np.min([_df_kde.shape[0], _area_center + _it + 1])][
                        'value'].sum() / _df_kde['value'].sum()

                if (_perc_data >= .6826) and (_sigma is None):
                    _sigma = _it + 0
                if (_perc_data >= .9544) and (_2_sigma is None):
                    _2_sigma = _it + 0
                    break
                if _it == _df_kde.shape[0] - 1:
                    _2_sigma = _it + 0

            _df_sigma = _df_kde.loc[
                        np.max([0, _area_center - _sigma]):np.min([_df_kde.shape[0], _area_center + _sigma])]
            _df_2_sigma_left = _df_kde.loc[
                               np.max([0, _area_center - _2_sigma]):np.min([_df_kde.shape[0], _area_center - _sigma])]
            _df_2_sigma_right = _df_kde.loc[
                                np.max([0, _area_center + _sigma]):np.min([_df_kde.shape[0], _area_center + _2_sigma])]

            _2_sigma_min = _df_2_sigma_left[_x_name].min()
            _2_sigma_max = _df_2_sigma_right[_x_name].max()
            if np.isnan(_2_sigma_min):
                _2_sigma_min = _df[_x_name].min()
            if np.isnan(_2_sigma_max):
                _2_sigma_max = _df[_x_name].max()

            _sigma_range = ': {:,.2f} to {:,.2f}'.format(_df_sigma[_x_name].min(), _df_sigma[_x_name].max())
            _2_sigma_range = ': {:,.2f} to {:,.2f}'.format(_2_sigma_min, _2_sigma_max)

            ax2.fill_between(_x_name, 'value', data=_df_sigma, color=sigma_color,
                             label=r'$1\sigma(68\%)$' + _sigma_range, alpha=alpha)
            ax2.fill_between(_x_name, 'value', data=_df_2_sigma_left, color=sigma_2_color,
                             label=r'$2\sigma(95\%)$' + _2_sigma_range, alpha=alpha)
            ax2.fill_between(_x_name, 'value', data=_df_2_sigma_right, color=sigma_2_color, label='__nolegend__',
                             alpha=alpha)
            ax2.legend(loc=legend_loc)

        # iterate over data so you can draw the lines
        if highlight_peaks:

            for _it, _row in _df_kde_ex.iterrows():

                _mu = _row[_x_name]
                _value_std = np.min([_row['value_min'], _row['value_max']])

                # stem (max)
                ax2.plot([_mu, _mu], [baseline, _row['value']], color=kde_color, label='__nolegend__', ls=':', **kwline)
                # std
                if highlight_peaks != 'max':
                    ax2.plot([_row['range_min'], _row['range_max']], [_value_std, _value_std],
                                                      color=kde_color, label='__nolegend__', ls=':', **kwline)

                # scatterplot for markers
                ax2.scatter(x=_mu, y=_row['value'], facecolor=kde_color, **kwargs)

                _mean_str = format(_mu, nr_format)
                _std_str = format(_row['range'] / 2., nr_format)

                _annotate = r'${}$'.format(_mean_str)
                if highlight_peaks != 'max':
                    _annotate += '\n' + r'$\pm{}$'.format(_std_str)

                ax2.annotate(_annotate, (_mu, _row['value']), ha=ha, va=va, xytext=(0, text_offset),
                             textcoords='offset points')

    if _twinx:
        ax2.legend(loc=legend_loc)
        ax2.set_axis_off()
    else:
        ax.legend(loc=legend_loc)

    return ax


def draw_ellipse(ax, *args, **kwargs):
    _e = patches.Ellipse(*args, **kwargs)
    ax.add_artist(_e)


def barplot_err(x, y, xerr=None, yerr=None, data=None, **kwargs):
    _data = []
    for _it in data.index:

        _data_i = pd.concat([data.loc[_it:_it]] * 3, ignore_index=True, sort=False)
        _row = data.loc[_it]

        if xerr is not None:
            _data_i[x] = [_row[x] - _row[xerr], _row[x], _row[x] + _row[xerr]]
        if yerr is not None:
            _data_i[y] = [_row[y] - _row[yerr], _row[y], _row[y] + _row[yerr]]
        _data.append(_data_i)

    _data = pd.concat(_data, ignore_index=True, sort=False)

    _ax = sns.barplot(x=x, y=y, data=_data, ci='sd', **kwargs)

    return _ax


def q_barplot(pd_series, ax=None, sort=False, percentage=False, **kwargs):
    _name = pd_series.name

    if ax is None:
        _, ax = plt.subplots(figsize=(16, 9 / 2))

    _df_plot = pd_series.value_counts().reset_index()

    if sort:
        _df_plot = _df_plot.sort_values(['index'])

    if percentage:

        _y_name = _name + '_perc'
        _df_plot[_y_name] = _df_plot[_name] / _df_plot[_name].sum() * 100
        _df_plot[_y_name] = _df_plot[_y_name].round(2)

    else:

        _y_name = _name

    sns.barplot(data=_df_plot, x='index', y=_y_name, ax=ax, **kwargs)

    return ax


def histplot(x=None, data=None, hue=None, hue_order=None, ax=None, bins=30, use_q_xlim=False, figsize=(16, 9 / 2),
             legend_kws=None, **kwargs):
    # long or short format
    if legend_kws is None:
        legend_kws = {}
    if data is not None:
        # avoid inplace operations
        _df_plot = data.copy()
        del data
        _x = x
    else:
        # create dummy df
        _df_plot = pd.DataFrame.from_dict({'x': x})
        _x = 'x'

    _xs = _df_plot[_x]

    # if applicable: filter data
    if use_q_xlim:
        _x_lim = q_plim(_xs)
        _df_plot = _df_plot[(_df_plot[_x] >= _x_lim[0]) & (_df_plot[_x] <= _x_lim[1])]
        _xs = _df_plot[_x]

    # create bins
    if not isinstance(bins, list):
        bins = np.linspace(_xs.min(), _xs.max(), bins)

    # if an axis has not been passed initialize one
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    # if a hue has been passed loop them
    if hue is not None:

        # if no hue order has been passed use default sorting
        if hue_order is None:
            hue_order = sorted(_df_plot[hue].unique())

        for _hue in hue_order:
            _xs = _df_plot[_df_plot[hue] == _hue][_x]

            ax.hist(_xs, label=_hue, alpha=.5, bins=bins, **kwargs)

        ax.legend(**legend_kws)

    else:

        ax.hist(_xs, bins=bins, **kwargs)

    return ax


def countplot(x=None, data=None, hue=None, ax=None, order='default', hue_order=None, normalize_x=False,
              normalize_hue=False, color=None, palette=None,
              x_tick_rotation=None, count_twinx=False, hide_legend=False, annotate=True,
              annotate_format=',.2f', figsize=(16, 9 / 2),
              legend_kws=None, barplot_kws=None, count_twinx_kws=None, **kwargs):
    # normalize_x causes the sum of each x group to be 100 percent
    # normalize_hue (with normalize=False) causes the sum of each hue group to be 100 percent

    # -- init

    # long or short format
    if legend_kws is None:
        legend_kws = {}
    if barplot_kws is None:
        barplot_kws = {}
    if count_twinx_kws is None:
        count_twinx_kws = {}
    if data is not None:
        # avoid inplace operations
        _df = data.copy()

        if x is None:
            _x = '_dummy'
            _df = _df.assign(_dummy=1)
        else:
            _x = x

    else:
        # create dummy df
        _df = pd.DataFrame.from_dict({'x': x})
        _x = 'x'

    _count_x = 'count_{}'.format(_x)
    _count_hue = 'count_{}'.format(hue)

    # if an axis has not been passed initialize one
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    if normalize_x:
        _y = 'perc_{}'.format(_x)
    elif normalize_hue:
        _y = 'perc_{}'.format(hue)
    else:
        _y = 'count'

    _df_count = df_count(x=_x, df=_df, hue=hue, **kwargs)

    if not is_list_like(order):
        if order == 'default':
            order = _df_count[[_x, _count_x]].drop_duplicates().sort_values(by=[_count_x], ascending=False)[_x]
        elif order == 'sorted':
            order = sorted(_df_count[_x].unique())
    if (hue_order == 'sorted') and (hue is not None):
        hue_order = sorted(_df_count[hue].unique())
    if (hue_order is None) and (hue is not None):
        hue_order = _df_count[[hue, _count_hue]].drop_duplicates().sort_values(by=[_count_hue], ascending=False)[hue]

    if palette is None:
        if color is None:
            palette = rcParams['palette']
        else:
            palette = [color]

    _plot = sns.barplot(data=_df_count, x=_x, y=_y, hue=hue, order=order, hue_order=hue_order, color=color,
                        palette=palette, ax=ax, **barplot_kws)

    # cleanup for x=None
    if x is None:
        ax.get_xaxis().set_visible(False)
        if normalize_x:
            ax.set_ylabel('perc')

    if hue is None and normalize_hue:
        ax.set_ylabel('perc')

    if annotate:
        # add annotation
        annotate_barplot(_plot, nr_format=annotate_format)
        # enlarge ylims
        _y_lim = list(ax.get_ylim())
        _y_lim[1] = _y_lim[1] * 1.1
        ax.set_ylim(_y_lim)

    if hide_legend:
        ax.get_legend().remove()
    elif hue is not None:
        ax.legend(**legend_kws)

    # tick rotation
    if x_tick_rotation is not None:
        ax.xaxis.set_tick_params(rotation=x_tick_rotation)

    # total count on secaxis
    if count_twinx:

        _ax = ax.twinx()

        count_twinx_kws_keys = list(count_twinx_kws.keys())

        if 'marker' not in count_twinx_kws_keys:
            count_twinx_kws['marker'] = '_'
        if 'color' not in count_twinx_kws_keys:
            count_twinx_kws['color'] = 'k'
        if 'alpha' not in count_twinx_kws_keys:
            count_twinx_kws['alpha'] = .5

        _ax.scatter(_x, _count_x, data=_df_count[[x, _count_x]].drop_duplicates(), **count_twinx_kws)
        _ax.set_ylabel('count')

    return ax


# quantile plot
def quantile_plot(x, data=None, qs=None, x2=None, hue=None, to_abs=False, ax=None,
                  figsize=(16, 9 / 2), **kwargs):
    # long or short format
    if qs is None:
        qs = [.1, .25, .5, .75, .9]
    if data is not None:
        # avoid inplace operations
        _df = data.copy()
        if x2 is None:
            _x = x
        else:
            _x = '{} - {}'.format(x, x2)
            _df[_x] = _df[x] - _df[x2]

    else:
        # create dummy df
        if x2 is None:
            _df = pd.DataFrame({'x': x})
            _x = 'x'
        else:
            _df = pd.DataFrame({'x': x, 'x2': x2}).eval('x_delta=x2-x')
            _x = 'x_delta'

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    _label = _x

    if to_abs:
        _df[_x] = _df[_x].abs()
        _label = '|{}|'.format(_x)

    if hue is None:
        _df_q = _df[_x].quantile(qs).reset_index()
    else:
        _hues = sorted(_df[hue].unique())

        _df_q = []

        for _hue in _hues:
            _df_i = _df[_df[hue] == _hue][_x].quantile(qs).reset_index()
            _df_i[hue] = _hue
            _df_q.append(_df_i)

        _df_q = pd.concat(_df_q, ignore_index=True, sort=False)

    sns.barplot(x='index', y=_x, data=_df_q, hue=hue, ax=ax, **kwargs)

    ax.set_xticklabels(['q{}'.format(int(_ * 100)) for _ in qs])
    ax.set_xlabel('')
    ax.set_ylabel(_label)

    return ax
