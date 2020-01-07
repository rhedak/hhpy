"""
hhpy.ds.py
~~~~~~~~~~~~~~~~

Contains DataScience functions extending on pandas and sklearn

"""

# standard imports
import numpy as np
import pandas as pd
import warnings

# third party imports
from copy import deepcopy
from scipy import stats, signal
from scipy.spatial import distance
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error, median_absolute_error
from sklearn.preprocessing import StandardScaler
from typing import Mapping, Sequence, Callable, Union, List

# local imports
from hhpy.main import export, force_list, tprint, progressbar, qformat, list_intersection, round_signif, is_list_like, \
    dict_list, append_to_dict_list, concat_cols


# --- pandas styles
@export
def highlight_max(df: pd.DataFrame, color: str = 'xkcd:cyan') -> pd.DataFrame:
    """
    highlights the largest value in each column of a pandas DataFrame

    :param df: pandas DataFrame
    :param color: color used for highlighting
    :return: the pandas DataFrame with the style applied to it
    """
    def cond_max(s: pd.Series):
        return ['background-color: {}'.format(color) if v else '' for v in s == s.max()]

    return df.style.apply(cond_max)


@export
def highlight_min(df: pd.DataFrame, color: str = 'xkcd:light red') -> pd.DataFrame:
    """
    highlights the smallest value in each column of a pandas DataFrame

    :param df: pandas DataFrame
    :param color: color used for highlighting
    :return: the pandas DataFrame with the style applied to it
    """
    def cond_min(s: pd.Series):
        return ['background-color: {}'.format(color) if v else '' for v in s == s.min()]

    return df.style.apply(cond_min)


@export
def highlight_max_min(df: pd.DataFrame, max_color: str = 'xkcd:cyan', min_color: str = 'xkcd:light red'):
    """
    highlights the largest and smallest value in each column of a pandas DataFrame

    :param df: pandas DataFrame
    :param max_color: color used for highlighting largest value
    :param min_color: color used for highlighting smallest value
    :return: the pandas DataFrame with the style applied to it
    """
    def cond_max_min(s):

        _out = []

        for _i in s:

            if _i == s.max():
                _out.append('background-color: {}'.format(max_color))
            elif _i == s.min():
                _out.append('background-color: {}'.format(min_color))
            else:
                _out.append('')

        return _out

    return df.style.apply(cond_max_min)


# --- functions
@export
def optimize_pd(df: pd.DataFrame, c_int: bool = True, c_float: bool = True, c_cat: bool = True, cat_frac: bool = .5) \
        -> pd.DataFrame:
    """
    optimize memory usage of a pandas df, automatically downcast all var types and converts objects to categories

    :param df: pandas DataFrame to be optimized. Other objects are implicitly cast to DataFrame
    :param c_int: whether to downcast integers
    :param c_float: whether to downcast floats
    :param c_cat: whether to cast objects to categories. Uses cat_frac as condition
    :param cat_frac: if c_cat is True and the column has less than cat_frac unique values it will be cast to category
    :return: the optimized pandas DataFrame
    """
    _df = pd.DataFrame(df).copy()
    del df

    # check for duplicate columns
    _duplicate_columns = get_duplicate_cols(_df)
    if len(_duplicate_columns) > 0:
        warnings.warn('duplicate columns found: {}'.format(_duplicate_columns))
        _df = drop_duplicate_cols(_df)

    if c_int:

        _df_int = _df.select_dtypes(include=['int'])

        for d_col in _df_int.columns:

            # you can only use unsigned if all values are positive
            if ~((_df_int[d_col] > 0).all()):
                _df_int = _df_int.drop(d_col, axis=1)

        converted_int = _df_int.apply(pd.to_numeric, downcast='unsigned')
        _df[converted_int.columns] = converted_int

    if c_float:
        _df_float = _df.select_dtypes(include=['float'])
        converted_float = _df_float.apply(pd.to_numeric, downcast='float')
        _df[converted_float.columns] = converted_float

    if c_cat:

        _df_obj = _df.select_dtypes(include=['object'])
        converted_obj = pd.DataFrame()

        for col in _df_obj.columns:

            num_unique_values = len(_df_obj[col].unique())
            num_total_values = len(_df_obj[col])

            if num_unique_values / num_total_values < (1 - cat_frac):
                converted_obj.loc[:, col] = _df_obj[col].astype('category')
            else:
                converted_obj.loc[:, col] = _df_obj[col]

        _df[converted_obj.columns] = converted_obj

    return _df


@export
def get_df_corr(df: pd.DataFrame, target: str = None, groupby: Union[str, list] = None) -> pd.DataFrame:
    """
    returns a pandas DataFrame containing all pearson correlations in a melted format

    :param df: input pandas DataFrame. Other objects are implicitly cast to DataFrame
    :param target: if target is specified: returns only correlations that involve the target column
    :param groupby: if groupby is specified: returns correlations for each level of the group
    :return: pandas DataFrame containing all pearson correlations in a melted format
    """
    # avoid inplace operations
    _df = df.copy()
    del df

    # if there is a column called index it will create problems so rename it to '__index__'
    _df = _df.rename({'index': '__index__'}, axis=1)

    # add dummy if no group by
    if groupby is None:
        groupby = ['_dummy']
        _df['_dummy'] = 1

    # setting target makes the df_corr only contain correlations that involve the target

    _cols = _df.select_dtypes(include=np.number).columns

    _df_corr = []

    for _index, _df_i in _df.groupby(groupby):

        # get corr
        _df_corr_i = _df_i.corr().reset_index().rename({'index': 'col_0'}, axis=1)

        # set upper right half to nan
        for _i in range(len(_cols)):
            _col = _cols[_i]

            _df_corr_i[_col] = np.where(_df_corr_i[_col].index <= _i, np.nan, _df_corr_i[_col])

        # gather / melt
        _df_corr_i = pd.melt(_df_corr_i, id_vars=['col_0'], var_name='col_1', value_name='corr').dropna()
        # drop self correlation
        _df_corr_i = _df_corr_i[_df_corr_i['col_0'] != _df_corr_i['col_1']]

        # get identifier
        for _groupby in force_list(groupby):
            _df_corr_i[_groupby] = _df_i[_groupby].iloc[0]

        _df_corr.append(_df_corr_i)

    _df_corr = df_merge(_df_corr)
    _df_corr = col_to_front(_df_corr, groupby)

    if '_dummy' in _df_corr.columns:
        _df_corr.drop('_dummy', axis=1, inplace=True)

    # reorder and keep only columns involving the target (if applicable)
    if target is not None:
        # if the target is col_1: switch it to col_0
        _target_is_col_1 = (_df_corr['col_1'] == target)
        _df_corr['col_1'] = np.where(_target_is_col_1, _df_corr['col_0'], _df_corr['col_1'])
        _df_corr['col_0'] = np.where(_target_is_col_1, target, _df_corr['col_0'])
        # keep only target in col_0
        _df_corr = _df_corr[_df_corr['col_0'] == target]

    # get absolute correlation
    _df_corr['corr_abs'] = np.abs(_df_corr['corr'])
    # sort descending
    _df_corr = _df_corr.sort_values(['corr_abs'], ascending=False).reset_index(drop=True)

    return _df_corr


@export
def drop_zero_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop columns with all 0 or None Values from DataFrame. Useful after applying one hot encoding.

    :param df: pandas DataFrame
    :return: pandas DataFrame without 0 columns.
    """
    # noinspection PyUnresolvedReferences
    return df[df.columns[(df != 0).any()]]


@export
def get_duplicate_indices(df: pd.DataFrame) -> Sequence:
    """
    Returns duplicate indices from a pandas DataFrame

    :param df: pandas DataFrame
    :return: List of indices that are duplicate
    """
    return df.index[df.index.duplicated()]


@export
def get_duplicate_cols(df: pd.DataFrame) -> Sequence:
    """
    Returns names of duplicate columns from a pandas DataFrame

    :param df: pandas DataFrame
    :return: List of column names that are duplicate
    """
    return df.columns[df.columns.duplicated()]


@export
def drop_duplicate_indices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop duplicate indices from pandas DataFrame

    :param df: pandas DataFrame
    :return: pandas DataFrame without the duplicates indices
    """
    return df.loc[~df.indices.duplicated(), :]


@export
def drop_duplicate_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop duplicate columns from pandas DataFrame

    :param df: pandas DataFrame
    :return: pandas DataFrame without the duplicates columns
    """
    return df.loc[:, ~df.columns.duplicated()]


@export
def change_span(s: pd.Series, steps: int = 5) -> pd.Series:
    """
    return a True/False series around a changepoint, used for filtering stepwise data series in a pandas df
    must be properly sorted!

    :param s: pandas Series or similar
    :param steps: number of steps around the changepoint to flag as true
    :return: pandas Series of dtype Boolean
    """
    return pd.Series(s.shift(-steps).ffill() != s.shift(steps).bfill())


@export
def outlier_to_nan(df: pd.DataFrame, col: str, groupby: Union[list, str] = None, std_cutoff: np.number = 3,
                   reps: int = 1, do_print: bool = False) -> pd.DataFrame:
    """
    this algorithm cuts off all points whose DELTA (avg diff to the prev and next point) is outside of the n std range

    :param df: pandas DataFrame
    :param col: column to be filtered
    :param groupby: if provided: applies std filter by group
    :param std_cutoff: the number of standard deviations outside of which to set values to None
    :param reps: how many times to repeat the algorithm
    :param do_print: whether to print steps to console
    :return: pandas DataFrame with outliers set to nan
    """
    _df = df.copy()
    del df

    if groupby is None:
        _df['__groupby'] = 1
        groupby = '__groupby'

    for _rep in range(reps):

        if do_print:
            tprint('rep = ' + str(_rep + 1) + ' of ' + str(reps))

        # grouped by df
        _df_out_grouped = _df.groupby(groupby)

        _df['_dummy'] = _df[col]
        # use interpolation to treat missing values
        _df['_dummy'] = _df_out_grouped['_dummy'].transform(pd.DataFrame.interpolate)

        # calculate delta (mean of diff to previous and next value)
        _df['_dummy_delta'] = .5 * (
                np.abs(_df['_dummy'] - _df_out_grouped['_dummy'].shift(1).bfill()) +
                np.abs(_df['_dummy'] - _df_out_grouped['_dummy'].shift(-1).ffill())
        )

        _df_mean = _df_out_grouped[['_dummy_delta']].mean().rename({'_dummy_delta': '_dummy_mean'}, axis=1)
        _df_std = _df_out_grouped[['_dummy_delta']].std().rename({'_dummy_delta': '_dummy_std'}, axis=1)
        _df_cutoff = _df_mean.join(_df_std).reset_index()

        _df = pd.merge(_df, _df_cutoff, on=groupby, how='inner')
        _df[col] = np.where(
            np.abs(_df['_dummy_delta'] - _df['_dummy_mean']) <= (std_cutoff * _df['_dummy_std']),
            _df[col], np.nan)

        _df = _df.drop(['_dummy', '_dummy_mean', '_dummy_std', '_dummy_delta'], axis=1)

    if '__groupby' in _df.columns:
        _df = _df.drop('__groupby', axis=1)

    return _df


@export
def butter_pass_filter(data: pd.Series, cutoff: int, fs: int, order: int, btype: str = None, shift: bool = False):
    """
    Implementation of a highpass / lowpass filter using scipy.signal.butter

    :param data: pandas Series or 1d numpy Array
    :param cutoff: cutoff
    :param fs: critical frequencies
    :param order: order of the fit
    :param btype: The type of filter. Passed to scipy.signal.butter.  Default is ‘lowpass’.
        One of {‘lowpass’, ‘highpass’, ‘bandpass’, ‘bandstop’}
    :param shift: whether to shift the data to start at 0
    :return: 1d numpy array containing the filtered data
    """

    def _f_butter_pass(_f_cutoff, _f_fs, _f_order, _f_btype):
        _nyq = 0.5 * _f_fs
        _normal_cutoff = _f_cutoff / _nyq
        # noinspection PyTupleAssignmentBalance
        __b, __a = signal.butter(_f_order, _normal_cutoff, btype=_f_btype, analog=False, output='ba')

        return __b, __a

    _data = np.array(data)

    if shift:
        _shift = pd.Series(data).iloc[0]
    else:
        _shift = 0

    _data -= _shift

    _b, _a = _f_butter_pass(_f_cutoff=cutoff, _f_fs=fs, _f_order=order, _f_btype=btype)

    _y = signal.lfilter(_b, _a, _data)

    _y = _y + _shift

    return _y


@export
def pass_by_group(df: pd.DataFrame, col: str, groupby: Union[str, list], btype: str, shift: bool = False,
                  cutoff: int = 1, fs: int = 20, order: int = 5):
    """
    allows applying a butter_pass filter by group

    :param df: pandas DataFrame
    :param col: column to filter
    :param groupby: columns to groupby
    :param btype: The type of filter. Passed to scipy.signal.butter.  Default is ‘lowpass’.
        One of {‘lowpass’, ‘highpass’, ‘bandpass’, ‘bandstop’}
    :param shift: shift: whether to shift the data to start at 0
    :param cutoff: cutoff
    :param fs: critical frequencies
    :param order: order of the filter
    :return: filtered DataFrame
    """
    _df = df.copy()
    del df

    _df_out_grouped = _df.groupby(groupby)

    # apply highpass filter
    _df[col] = np.concatenate(
        _df_out_grouped[col].apply(butter_pass_filter, cutoff, fs, order, btype, shift).values).flatten()

    _df = _df.reset_index(drop=True)

    return _df


@export
def lfit(x: Union[pd.Series, str], y: Union[pd.Series, str] = None, w: Union[pd.Series, str] = None,
         df: pd.DataFrame = None, groupby: Union[list, str] = None, do_print: bool = True,
         catch_error: bool = False, return_df: bool = False, extrapolate: bool = None):
    """
    quick linear fit with numpy

    :param x: names of x variables in df or vector data, if y is None treated as target and fit against the index
    :param y: names of y variables in df or vector data [optional]
    :param w: names of weight variables in df or vector data [optional]
    :param df: pandas DataFrame containing x,y,w data [optional]
    :param groupby: If specified the linear fit is applied by group [optional]
    :param do_print: whether to print steps to console
    :param catch_error: whether to keep going in case of error [optional]
    :param return_df: whether to return a DataFrame or Series [optional]
    :param extrapolate: how many iteration to extrapolate [optional]
    :return: if return_df is True: pandas DataFrame, else: pandas Series
    """
    if df is None:
        if 'name' in dir(x):
            _x_name = x.name
        else:
            _x_name = 'x'
        if 'name' in dir(y):
            _y_name = y.name
        else:
            _y_name = 'x'
        if 'name' in dir(w):
            _w_name = w.name
        else:
            _w_name = 'x'
        _df = pd.DataFrame({
            _x_name: x,
            _y_name: y,
            _w_name: w
        })
    else:
        _df = df.copy()
        del df
        _x_name = x
        _y_name = y
        _w_name = w
    _y_name_fit = '{}_fit'.format(_y_name)

    if groupby is None:
        groupby = '__groupby'
        _df[groupby] = 1

    _it_max = _df[groupby].drop_duplicates().shape[0]

    _df_fit = []

    for _it, (_index, _df_i) in enumerate(_df.groupby(groupby)):

        if do_print and _it_max > 1:
            progressbar(_it, _it_max, print_prefix=qformat(_index))

        if y is None:
            _x = _df_i.index
            _y = _df_i[_x_name]
        else:
            _x = _df_i[_x_name]
            _y = _df_i[_y_name]
        if w is not None:
            _w = _df_i[_w_name]
            _w = _w.astype(float)
        else:
            _w = None

        _x = _x.astype(float)
        _y = _y.astype(float)

        _idx = np.isfinite(_x) & np.isfinite(_y)

        if _w is not None:
            _w_idx = _w[_idx]
        else:
            _w_idx = None

        if catch_error:
            try:
                _fit = np.poly1d(np.polyfit(x=_x[_idx], y=_y[_idx], deg=1, w=_w_idx))
            except Exception as _exc:
                warnings.warn('handled exception: {}'.format(_exc))
                _fit = None
        else:
            _fit = np.poly1d(np.polyfit(x=_x[_idx], y=_y[_idx], deg=1, w=_w_idx))

        _x_diff = _x.diff().mean()
        _x = list(_x)
        _y = list(_y)

        if _fit is None:
            _y_fit = _y
        else:

            if extrapolate is not None:

                for _ext in range(extrapolate):
                    _x.append(np.max(_x) + _x_diff)
                    _y.append(np.nan)

            _y_fit = _fit(_x)

        _df_i[_x_name] = _x
        _df_i[_y_name] = _y
        _df_i[_y_name_fit] = _y_fit

        _df_fit.append(_df_i)

    _df_fit = df_merge(_df_fit)

    if do_print and _it_max > 1:
        progressbar()

    if return_df:
        return _df_fit
    else:
        return _df_fit[_y_name_fit]


@export
def qf(df: pd.DataFrame, fltr: Union[pd.DataFrame, pd.Series, Mapping], remove_unused_categories: bool = True,
       reset_index: bool = False):
    """
    quickly filter a DataFrame based on equal criteria. All columns of fltr present in df are filtered
    to be equal to the first entry in filter_df.

    :param df: pandas DataFrame to be filtered
    :param fltr: filter condition as DataFrame or Mapping or Series
    :param remove_unused_categories: whether to remove unused categories from categorical dtype after filtering
    :param reset_index: whether to reset index after filtering
    :return: filtered pandas DataFrame
    """
    _df = df.copy()
    del df

    # filter_df can also be a dictionary, in which case pd.DataFrame.from_dict will be applied
    if isinstance(fltr, Mapping):
        _filter_df = pd.DataFrame(fltr, index=[0])
    # if the filter_df is a series, attempt to cast to data frame
    elif isinstance(fltr, pd.Series):
        _filter_df = pd.DataFrame(fltr).T
    # assume it to be a DataFrame
    else:
        _filter_df = fltr.copy()
        del fltr

    # drop columns not in
    _filter_df = _filter_df[list_intersection(_filter_df.columns, _df.columns)]

    # init filter
    _filter_iloc = _filter_df.iloc[0]

    # create a dummy boolean of all trues with len of df
    _filter_condition = (_df.index == _df.index)

    # logical and filter for all columns in filter df
    for _col in _filter_df.columns:

        _filter_condition = _filter_condition & (_df[_col] == _filter_iloc[_col])

    # create filtered df
    _df = _df[_filter_condition]

    # remove_unused_categories
    if remove_unused_categories:

        for _cat in _df.select_dtypes(include='category').columns:
            _df[_cat] = _df[_cat].cat.remove_unused_categories()

    if reset_index:
        _df = _df.reset_index(drop=True)

    # return
    return _df


@export
def quantile_split(s: pd.Series, n: int, signif: int = 2, na_to_med: bool = False):
    """
    splits a numerical column into n quantiles. Useful for mapping numerical columns to categorical columns

    :param s: pandas Series to be split
    :param n: number of quantiles to split into
    :param signif: number of significant digits to round to
    :param na_to_med: whether to fill na values with median values
    :return: pandas Series of dtype category
    """
    if len(s.unique()) <= n:
        return s

    _s = pd.Series(s).copy().astype(float)
    _s = np.where(~np.isfinite(_s), np.nan, _s)
    _s = pd.Series(_s)

    _s_out = _s.apply(lambda _: np.nan)

    if na_to_med:
        _s = _s.fillna(_s.median())

    if signif is not None:
        _s = round_signif(_s, signif)

    if not isinstance(_s, pd.Series):
        _s = pd.Series(_s)

    _i = -1

    for _q in np.arange(0, 1, 1. / n):

        _i += 1

        __q_min = np.quantile(_s.dropna().values, _q)

        if _q + .1 >= 1:
            __q_max = _s.max()
        else:
            __q_max = np.quantile(_s.dropna().values, _q + .1)

        if np.round(_q + .1, 1) == 1.:
            __q_max_adj = np.inf
            _right_equal_sign = '<='
        else:
            __q_max_adj = __q_max
            _right_equal_sign = '<'

        _q_name = 'q{}: {}<=_{}{}'.format(_i, round_signif(__q_min, signif), _right_equal_sign,
                                          round_signif(__q_max, signif))

        _s_out = np.where((_s >= __q_min) & (_s < __q_max_adj), _q_name, _s_out)

    # get back the old properties of the series (or you'll screw the index)
    _s_out = pd.Series(_s_out)
    _s_out.name = s.name
    _s_out.index = s.index

    # convert to cat
    _s_out = _s_out.astype('category')

    return _s_out


@export
def acc(y_true: Union[pd.Series, str], y_pred: Union[pd.Series, str], df: pd.DataFrame = None) -> float:
    """
    calculate accuracy for a categorical label

    :param y_true: true values as name of df or vector data
    :param y_pred: predicted values as name of df or vector data
    :param df: pandas DataFrame containing true and predicted values [optional]
    :return: accuracy a percentage
    """
    if df is None:

        _y_true = y_true
        _y_pred = y_pred

    else:

        _y_true = df[y_true]
        _y_pred = df[y_pred]

    _acc = np.sum(_y_true == _y_pred) / len(_y_true)
    return _acc


@export
def rel_acc(y_true: Union[pd.Series, str], y_pred: Union[pd.Series, str], df: pd.DataFrame = None,
            target_class: str = None):
    """
    relative accuracy of the prediction in comparison to predicting everything as the most common group
    :param y_true: true values as name of df or vector data
    :param y_pred: predicted values as name of df or vector data
    :param df: pandas DataFrame containing true and predicted values [optional]
    :param target_class: name of the target class, by default the most common one is used [optional]
    :return: accuracy difference as percent
    """
    if df is None:

        _y_true = 'y_true'
        _y_pred = 'y_pred'

        _df = pd.DataFrame({
            _y_true: y_true,
            _y_pred: y_pred
        })

    else:

        _df = df.copy()

        _y_true = y_true
        _y_pred = y_pred

        del df, y_true, y_pred

    if target_class is None:
        # get acc of pred
        _acc = acc(_y_true, _y_pred, df=_df)
        # get percentage of most common value
        _acc_mc = _df[_y_true].value_counts()[0] / _df.shape[0]
    else:
        _df_target_class = _df.query('{}=="{}"'.format(_y_true, target_class))
        # get acc of pred for target class
        _acc = acc(_y_true, _y_pred, df=_df_target_class)
        # get percentage of target class
        _acc_mc = _df_target_class.shape[0] / _df.shape[0]

    # rel acc is diff of both
    return _acc - _acc_mc


@export
def cm(y_true: Union[pd.Series, str], y_pred: Union[pd.Series, str], df: pd.DataFrame = None) -> pd.DataFrame:
    """
    confusion matrix from pandas df
    :param y_true: true values as name of df or vector data
    :param y_pred: predicted values as name of df or vector data
    :param df: pandas DataFrame containing true and predicted values [optional]
    :return: Confusion matrix as pandas DataFrame
    """
    if df is None:

        _y_true = deepcopy(y_true)
        _y_pred = deepcopy(y_pred)

        if 'name' in dir(y_true):
            y_true = y_true.name
        else:
            y_true = 'y_true'
        if 'name' in dir(y_pred):
            y_pred = y_pred.name
        else:
            y_true = 'y_pred'
        df = pd.DataFrame({
            y_true: _y_true,
            y_pred: _y_pred
        })
    else:
        _y_true = df[y_true]
        _y_pred = df[y_pred]

    _cm = df.eval('_count=1').groupby([y_true, y_pred]).agg({'_count': 'count'}).reset_index() \
        .pivot_table(index=y_true, columns=y_pred, values='_count')
    _cm = _cm.fillna(0).astype(int)

    return _cm


@export
def f1_pr(y_true: Union[pd.Series, str], y_pred: Union[pd.Series, str], df: pd.DataFrame = None, target: str = None,
          factor: int = 100) -> pd.DataFrame:
    """
    get f1 score, true positive, true negative, missed positive and missed negative rate

    :param y_true: true values as name of df or vector data
    :param y_pred: predicted values as name of df or vector data
    :param df: pandas DataFrame containing true and predicted values [optional]
    :param target: level for which to return the rates, by default all levels are returned [optional]
    :param factor: factor by which to scale results, default 100 [optional]
    :return: pandas DataFrame containing f1 score, true positive, true negative, missed positive
        and missed negative rate
    """
    if df is None:

        _y_true = deepcopy(y_true)
        _y_pred = deepcopy(y_pred)

        if 'name' in dir(y_true):
            y_true = y_true.name
        else:
            y_true = 'y_true'
        if 'name' in dir(y_pred):
            y_pred = y_pred.name
        else:
            y_true = 'y_pred'
        df = pd.DataFrame({
            y_true: _y_true,
            y_pred: _y_pred
        })
    else:
        _y_true = df[y_true]
        _y_pred = df[y_pred]

    _cm = cm(y_true=y_true, y_pred=y_pred, df=df)

    if target is None:
        target = _cm.index.tolist()
    elif not is_list_like(target):
        target = [target]

    _f1_pr = []

    _tp_sum = 0
    _tn_sum = 0
    _mp_sum = 0
    _mn_sum = 0
    _count_true_sum = 0

    for _target in target:

        if _target in _cm.index:
            _count_true = _cm.loc[_target].sum()
        else:
            _count_true = 0

        _count_true_sum += _count_true

        if _target in _cm.columns:
            _count_pred = _cm[_target].sum()
        else:
            _count_pred = 0

        _perc_pred = _count_pred / _count_true * factor

        # true positive: out of predicted as target how many are actually target
        try:
            _tp_i = _cm[_target][_target]
            _tp_sum += _tp_i
        except ValueError:
            _tp_i = np.nan
        # false positive: out of predicted as not target how many are actually not target
        try:
            _tn_i = _cm.drop(_target, axis=1).drop(_target, axis=0).sum().sum()
            _tn_sum += _tn_i
        except ValueError:
            _tn_i = np.nan

        # missed positive: out of true target how many were predicted as not target
        try:
            _mp_i = _cm.drop(_target, axis=1).loc[_target].sum()
            _mp_sum += _mp_i
        except ValueError:
            _mp_i = np.nan
        # missed negative: out of true not target how many were predicted as target
        try:
            _mn_i = _cm.drop(_target, axis=0)[_target].sum()
            _mn_sum += _mn_i
        except ValueError:
            _mn_i = np.nan

        # precision
        try:
            _precision = _tp_i / (_tp_i + _mn_i) * 100
        except ValueError:
            _precision = np.nan

        # recall
        try:
            _recall = _tp_i / (_tp_i + _mp_i) * 100
        except ValueError:
            _recall = np.nan

        if np.isnan(_precision) or np.isnan(_recall):
            _f1 = np.nan
        else:
            _f1 = 200 * (_precision / 100. * _recall / 100.) / (_precision / 100. + _recall / 100.)

        # to df
        _cm_target = pd.DataFrame({
            y_true: [_target], 'count': [_count_true], 'F1': [_f1], 'precision': [_precision], 'recall': [_recall]
        }).copy()

        _f1_pr.append(_cm_target)

    _f1_pr = pd.concat(_f1_pr, ignore_index=True, sort=False).set_index(y_true)

    return _f1_pr


@export
def f_score(y_true: Union[pd.Series, str], y_pred: Union[pd.Series, str], df: pd.DataFrame = None, dropna: bool = False,
            f: Callable = r2_score, groupby: Union[list, str] = None, f_name: str = None) -> Union[pd.DataFrame, float]:
    """
    generic scoring function base on pandas DataFrame.

    :param y_true: true values as name of df or vector data
    :param y_pred: predicted values as name of df or vector data
    :param df: pandas DataFrame containing true and predicted values [optional]
    :param dropna: whether to dropna values [optional]
    :param f: scoreing function to apply, default is sklearn.metrics.r2_score, should return a scalar value. [optional]
    :param groupby: if supplied then the result is returned for each group level [optional]
    :param f_name: name of the scoreing function, by default uses .__name__ property of fuction [optional]
    :return: if groupby is supplied: pandas DataFrame, else: scalar value
    """
    if df is None:

        _df = pd.DataFrame()

        _y_true = 'y_true'
        _y_pred = 'y_pred'
        _df[_y_true] = y_true
        _df[_y_pred] = y_pred

    else:

        _y_true = y_true
        _y_pred = y_pred

        _df = df.copy()
        del df

    if dropna:
        _df = _df.dropna(subset=[_y_true, _y_pred])
        if groupby is not None:
            _df = _df.dropna(subset=groupby)
    if _df.shape[0] == 0:
        return np.nan

    if groupby is None:

        return f(_df[_y_true], _df[_y_pred])

    else:

        _df_out = []

        for _i, _df_group in _df.groupby(groupby):

            _df_i = _df_group[force_list(groupby)].head(1)
            if f_name is None:
                f_name = f.__name__
            _df_i[f_name] = f(_df_group[_y_true], _df_group[_y_pred])
            _df_out.append(_df_i)

        _df_out = df_merge(_df_out)

        return _df_out


# shorthand r2
@export
def r2(*args, **kwargs) -> Union[pd.DataFrame, float]:
    """
    wrapper for f_score using sklearn.metrics.r2_score

    :param args: passed to f_score
    :param kwargs: passed to f_score
    :return: if groupby is supplied: pandas DataFrame, else: scalar value
    """
    return f_score(*args, f=r2_score, **kwargs)


@export
def rmse(*args, **kwargs) -> Union[pd.DataFrame, float]:
    """
    wrapper for f_score using numpy.sqrt(skearn.metrics.mean_squared_error)

    :param args: passed to f_score
    :param kwargs: passed to f_score
    :return: if groupby is supplied: pandas DataFrame, else: scalar value
    """
    def _f_rmse(x, y):
        return np.sqrt(mean_squared_error(x, y))

    return f_score(*args, f=_f_rmse, **kwargs)


@export
def mae(*args, **kwargs) -> Union[pd.DataFrame, float]:
    """
    wrapper for f_score using skearn.metrics.mean_absolute_error

    :param args: passed to f_score
    :param kwargs: passed to f_score
    :return: if groupby is supplied: pandas DataFrame, else: scalar value
    """
    return f_score(*args, f=mean_absolute_error, **kwargs)


@export
def stdae(*args, **kwargs) -> Union[pd.DataFrame, float]:
    """
    wrapper for f_score using the standard deviation of the absolute error

    :param args: passed to f_score
    :param kwargs: passed to f_score
    :return: if groupby is supplied: pandas DataFrame, else: scalar value
    """
    def _f_stdae(x, y):
        return np.std(np.abs(x - y))

    return f_score(*args, f=_f_stdae, **kwargs)


@export
def medae(*args, **kwargs) -> Union[pd.DataFrame, float]:
    """
    wrapper for f_score using skearn.metrics.median_absolute_error

    :param args: passed to f_score
    :param kwargs: passed to f_score
    :return: if groupby is supplied: pandas DataFrame, else: scalar value
    """
    return f_score(*args, f=median_absolute_error, **kwargs)


@export
def corr(*args, **kwargs) -> Union[pd.DataFrame, float]:
    """
    wrapper for f_score using pandas.Series.corr

    :param args: passed to f_score
    :param kwargs: passed to f_score
    :return: if groupby is supplied: pandas DataFrame, else: scalar value
    """
    def _f_corr(x, y): return pd.Series(x).corr(other=pd.Series(y))

    return f_score(*args, f=_f_corr, **kwargs)


@export
def df_score(df: pd.DataFrame, y_true: str, pred_suffix: list = None, scores: list = None, pivot: bool = True,
             scale: Union[dict, list, int] = None, groupby: Union[list, str] = None) -> pd.DataFrame:
    """
    creates a DataFrame displaying various kind of scores

    :param df: pandas DataFrame containing the true, pred data
    :param y_true: name of the true variable inside df
    :param pred_suffix: name of the predicted variable suffixes. Supports multiple predictions.
        By default assumed suffix 'pred' [optional]
    :param scores: scoring functions to be used [optional]
    :param pivot: whether to pivot the DataFrame for easier readability [optional]
    :param scale: a scale for multiplying the scores, default 1 [optional]
    :param groupby: if supplied then the scores are calculated by group [optional]
    :return: pandas DataFrame containing al the scores
    """
    if pred_suffix is None:
        pred_suffix = ['pred']
    if scores is None:
        scores = ['r2', 'rmse', 'mae', 'stdae', 'medae']
    _df = df.copy()
    del df

    if groupby is None:
        _groupby = ['_dummy']
        _df['_dummy'] = 1
    else:
        _groupby = force_list(groupby)

    _target = force_list(y_true)
    _model_names = force_list(pred_suffix)

    if isinstance(scale, Mapping):
        for _key, _value in scale.items():
            _df[_key] *= _value
            for _model_name in _model_names:
                _df['{}_{}'.format(_key, _model_name)] *= _value
    elif is_list_like(scale):
        _i = -1
        # noinspection PyTypeChecker
        for _scale in scale:
            _i += 1
            _df[_target[_i]] *= _scale
            for _model_name in _model_names:
                _df['{}_{}'.format(_target[_i], _model_name)] *= _scale
    elif scale is not None:
        for _y_ref in _target:
            _df[_y_ref] *= scale
            for _model_name in _model_names:
                _df['{}_{}'.format(_y_ref, _model_name)] *= scale

    _df_score = dict_list(_groupby + ['y_ref', 'model', 'score', 'value'])
    for _y_ref in _target:
        for _model_name in _model_names:
            for _score in scores:

                _y_ref_pred = '{}_{}'.format(_y_ref, _model_name)
                if _y_ref_pred not in _df.columns:
                    raise KeyError('{} not in columns'.format(_y_ref_pred))

                if isinstance(_score, str):
                    _score = eval(_score)

                for _index, _df_i in _df.groupby(_groupby):

                    _value = _score(_y_ref, _y_ref_pred, df=_df_i)

                    _append_dict = {
                        'y_ref': _y_ref,
                        'model': _model_name,
                        'score': _score.__name__,
                        'value': _value
                    }

                    for _groupby_i in _groupby:
                        _append_dict[_groupby_i] = _df_i[_groupby_i].iloc[0]

                    append_to_dict_list(_df_score, _append_dict)

    _df_score = pd.DataFrame(_df_score)

    _pivot_index = ['y_ref', 'model']

    if groupby is None:
        _df_score = _df_score.drop(['_dummy'], axis=1)
    else:
        _pivot_index += _groupby

    if pivot:
        _df_score = _df_score.pivot_table(index=_pivot_index, columns='score', values='value')

    return _df_score


@export
def rmsd(x: str, df: pd.DataFrame, group: str, return_df_paired: bool = False, agg_func: str = 'median',
         standardize: bool = False, to_abs: bool = False) -> Union[float, pd.DataFrame]:
    """
    calculated the weighted root mean squared difference for a reference columns x by a specific group

    :param x: name of the column to calculate the rmsd for
    :param df: pandas DataFrame
    :param group: groups for which to calculate the rmsd
    :param return_df_paired: whether to return the paired DataFrame
    :param agg_func: which aggregation to use for the group value, passed to pd.DataFrame.agg
    :param standardize: whether to apply Standardization before calculating the rmsd
    :param to_abs: whether to cast x to abs before calculating the rmsd
    :return: if return_df_paired pandas DataFrame, else rmsd as float
    """

    _agg_by_group = '{}_by_group'.format(agg_func)

    _df = df.copy()

    if to_abs:
        _df[x] = _df[x].abs()
    if standardize:
        _df[x] = (_df[x] - _df[x].mean()) / _df[x].std()

    _df = _df.groupby([group]).agg({x: ['count', agg_func]}).reset_index()
    _df.columns = ['group', 'count', _agg_by_group]
    _df['dummy'] = 1

    _df_paired = pd.merge(_df, _df, on='dummy')
    _df_paired = _df_paired[_df_paired['group_x'] != _df_paired['group_y']]
    _df_paired['weight'] = _df_paired['count_x'] * _df_paired['count_y']
    _df_paired['difference'] = _df_paired[_agg_by_group + '_x'] - _df_paired[_agg_by_group + '_y']
    _df_paired['weighted_squared_difference'] = _df_paired['weight'] * _df_paired['difference'] ** 2

    if return_df_paired:
        return _df_paired
    else:
        return np.sqrt(_df_paired['weighted_squared_difference'].sum() / _df_paired['weight'].sum())


# get a data frame showing the root mean squared difference by group type
@export
def df_rmsd(x: str, df: pd.DataFrame, groups: Union[list, str] = None, hue: str = None, hue_order: list = None,
            sort_by_hue: bool = True, n_quantiles: int = 10, include_rmsd: bool = True, **kwargs):
    """
    calculate rmsd for reference column x with multiple other columns and return as DataFrame

    :param x: name of the column to calculate the rmsd for
    :param df: pandas DataFrame containing the data
    :param groups: groups to calculate the rmsd or, defaults to all other columns in the DataFrame [optional]
    :param hue: further calculate the rmsd for each hue level [optional]
    :param hue_order: sort the hue levels in this order [optional]
    :param sort_by_hue: sort the values by hue rather than by group [optional]
    :param n_quantiles: numeric columns will be automatically split into this many quantiles [optional]
    :param include_rmsd: if False provide only a grouped DataFrame but don't actually calculate the rmsd,
        you can use include_rmsd=False to save computation time if you only need the maxperc (used in plotting)
    :param kwargs: passed to rmsd
    :return: None
    """
    # avoid inplace operations
    _df = df.copy()

    _df_rmsd = pd.DataFrame()

    # x /  groups can be a list or a scaler
    if isinstance(x, list):
        _x_list = x
    else:
        _x_list = [x]

    if groups is None:
        groups = [_col for _col in _df.columns if _col not in _x_list]

    if isinstance(groups, list):
        _groups = groups
    else:
        _groups = [groups]

    if hue is not None:
        if hue in list(_df.select_dtypes(include=np.number)):
            _df[hue] = quantile_split(_df[hue], n_quantiles)
        _df[hue] = _df[hue].astype('category').cat.remove_unused_categories()
        _hues = _df[hue].cat.categories
    else:
        _hues = [None]

    # loop x
    for _x in _x_list:

        # loop groups
        for _group in _groups:

            # eliminate self dependency
            if _group == _x:
                continue

            # numerical data is split in quantiles
            if _group in list(_df.select_dtypes(include=np.number)):
                _df['_group'] = quantile_split(_df[_group], n_quantiles)
            # other data is taken as is
            else:
                _df['_group'] = _df[_group].copy()

            warnings.simplefilter(action='ignore', category=RuntimeWarning)

            # if hue is None, one calculation is enough
            for _hue in _hues:

                if hue is None:
                    _df_hue = _df
                else:
                    _df_hue = _df[_df[hue] == _hue]

                if include_rmsd:
                    _rmsd = rmsd(x=_x, df=_df_hue, group='_group', **kwargs)
                else:
                    _rmsd = np.nan

                _count = len(_df_hue['_group'])
                _maxcount = _df_hue['_group'].value_counts().reset_index()['_group'].iloc[0]
                _maxperc = _maxcount / _count
                _maxlevel = _df_hue['_group'].value_counts().reset_index()['index'].iloc[0]

                _df_rmsd_hue = pd.DataFrame(
                    {'x': _x, 'group': _group, 'rmsd': _rmsd, 'maxperc': _maxperc, 'maxlevel': _maxlevel,
                     'maxcount': _maxcount, 'count': _count}, index=[0])
                if hue is not None:
                    _df_rmsd_hue[hue] = _hue

                _df_rmsd = _df_rmsd.append(_df_rmsd_hue, ignore_index=True, sort=False)

    # postprocessing, sorting etc.
    if hue is not None:

        _df_rmsd[hue] = _df_rmsd[hue].astype('category')

        if hue_order is not None:
            _hues = hue_order
        else:
            _hues = _df_rmsd[hue].cat.categories

        _df_order = _df_rmsd[_df_rmsd[hue] == _hues[0]].sort_values(by=['rmsd'], ascending=False).reset_index(
            drop=True).reset_index().rename({'index': '_order'}, axis=1)[['group', '_order']]
        _df_rmsd = pd.merge(_df_rmsd, _df_order)

        if sort_by_hue:
            _df_rmsd = _df_rmsd.sort_values(by=[hue, '_order']).reset_index(drop=True).drop(['_order'], axis=1)
        else:
            _df_rmsd = _df_rmsd.sort_values(by=['_order', hue]).reset_index(drop=True).drop(['_order'], axis=1)
    else:
        _df_rmsd = _df_rmsd.sort_values(by=['rmsd'], ascending=False).reset_index(drop=True)

    return _df_rmsd


@export
def df_p(x: str, group: str, df: pd.DataFrame, hue: str = None, agg_func: str = 'mean', agg: bool = False,
         n_quantiles: int = 10):
    """
    returns a DataFrame with the p value. See hypothesis testing.
    :param x: name of column to evaluate
    :param group: name of grouping column
    :param df: pandas DataFrame
    :param hue: further split by hue level
    :param agg_func: standard agg function, passed to pd.DataFrame.agg
    :param agg: whether to include standard aggregation
    :param n_quantiles: numeric columns will be automatically split into this many quantiles [optional]
    :return: pandas DataFrame containing p values
    """
    # numeric to quantile
    _df, _groupby, _groupby_names, _vars, _df_levels, _levels = df_group_hue(df, group=group, hue=hue, x=x,
                                                                               n_quantiles=n_quantiles)

    _df_p = pd.DataFrame()

    # Loop levels
    for _i_1 in range(len(_levels)):
        for _i_2 in range(len(_levels)):

            _level_1 = _levels[_i_1]
            _level_2 = _levels[_i_2]

            if _level_1 != _level_2:

                _s_1 = _df[_df['_label'] == _level_1][x].dropna()
                _s_2 = _df[_df['_label'] == _level_2][x].dropna()

                # get t test / median test
                try:
                    if agg_func == 'median':
                        _p = stats.median_test(_s_1, _s_2)[1]  # ,nan_policy='omit'
                    else:
                        _p = stats.ttest_ind(_s_1, _s_2, equal_var=False)[1]
                except ValueError:
                    _p = np.nan
                # TODO handle other cases than median / mean ?

                _df_dict = {}

                if hue is not None:

                    _df_dict[group] = _df_levels['_group'][_i_1]
                    _df_dict[group + '_2'] = _df_levels['_group'][_i_2]
                    _df_dict[hue] = _df_levels['_hue'][_i_1]
                    _df_dict[hue + '_2'] = _df_levels['_hue'][_i_1]

                else:

                    _df_dict[group] = _level_1
                    _df_dict[group + '_2'] = _level_2

                _df_dict['p'] = _p

                _df_p = _df_p.append(pd.DataFrame(_df_dict, index=[0]), ignore_index=True, sort=False)

    if agg:
        _df_p = _df_p.groupby(_groupby).agg({'p': 'mean'}).reset_index()

    return _df_p


# df with various aggregations
def df_agg(x, group, df, hue=None, agg=None, n_quantiles=10, na_to_med=False, p=True,
           p_test='mean', sort_by_count=False):
    if agg is None:
        agg = ['mean', 'median', 'std']
    if not isinstance(agg, list):
        agg = [agg]

    # numeric to quantile
    _df, _groupby, _groupby_names, _vars, _df_levels, _levels = df_group_hue(df, group=group, hue=hue, x=x,
                                                                               n_quantiles=n_quantiles,
                                                                               na_to_med=na_to_med)

    if hue is not None:
        _hue = '_hue'
    else:
        _hue = None

    # get agg
    _df_agg = _df.groupby(_groupby).agg({'_dummy': 'count', x: agg}).reset_index()
    _df_agg.columns = _groupby + ['count'] + agg
    if sort_by_count:
        _df_agg = _df_agg.sort_values(by=['count'], ascending=False)

    if p:
        _df_p = df_p(x=x, group='_group', hue=_hue, df=_df, agg_func=p_test, agg=True)
        _df_agg = pd.merge(_df_agg, _df_p, on=_groupby)

    _df_agg.columns = _groupby_names + [_col for _col in _df_agg.columns if _col not in _groupby]

    return _df_agg


# quick function to adjust group and hue to be categorical
def df_group_hue(df, group, hue=None, x=None, n_quantiles=10, na_to_med=False, keep=True):
    _df = df.copy()
    _hue = None

    if keep:
        _group = '_group'
        if hue is not None:
            _hue = '_hue'
    else:
        _group = group
        if hue is not None:
            _hue = hue

    _groupby = ['_group']
    _groupby_names = [group]
    _vars = [group]

    if hue is not None:
        _groupby.append('_hue')
        _groupby_names.append(hue)
        if hue not in _vars:
            _vars.append(hue)

    if x is not None:
        if x not in _vars:
            _vars = [x] + _vars

    _df = _df.drop([_col for _col in _df.columns if _col not in _vars], axis=1)

    _df[_group] = _df[group].copy()
    if hue is not None:
        _df[_hue] = _df[hue].copy()
    _df['_dummy'] = 1

    _df[_group] = _df[group].copy()
    if hue is not None:
        _df[_hue] = _df[hue].copy()

    # - numeric to quantile
    # group
    if _group in list(_df.select_dtypes(include=np.number)):
        _df[_group] = quantile_split(_df[group], n_quantiles, na_to_med=na_to_med)
    _df[_group] = _df[_group].astype('category').cat.remove_unused_categories()

    # hue
    if hue is not None:
        if _hue in list(_df.select_dtypes(include=np.number)):
            _df[_hue] = quantile_split(_df[hue], n_quantiles, na_to_med=na_to_med)
        _df[_hue] = _df[_hue].astype('category').cat.remove_unused_categories()
        _df['_label'] = concat_cols(_df, [_group, _hue]).astype('category')
        _df_levels = _df[[_group, _hue, '_label']].drop_duplicates().reset_index(drop=True)
        _levels = _df_levels['_label']
    else:
        _df['_label'] = _df[_group]
        _df_levels = _df[[_group, '_label']].drop_duplicates().reset_index(drop=True)
        _levels = _df_levels['_label']

    return _df, _groupby, _groupby_names, _vars, _df_levels, _levels


def order_cols(df, cols):
    return df[cols + [_col for _col in df.columns if _col not in cols]]


def df_precision_filter(df, col, precision):
    return df[(np.abs(df[col] - df[col].round(precision)) < (1 / (2 * 10 ** (precision + 1))))]


# grouped iterpolate method (avoids .apply failing if one sub group fails)
def grouped_interpolate(df, col, groupby, method=None):
    _df = df.copy()

    _dfs_i = []

    for _index_i, _df_i in df.groupby(groupby):

        try:
            _df_i[col] = _df_i[col].interpolate(method=method)
        except ValueError:  # do nothing
            _df_i[col] = _df_i[col]

        _dfs_i.append(_df_i)

    _df_interpolate = pd.concat(_dfs_i)

    return _df_interpolate[col]


def time_reg(df, t='t', y='y', t_unit='D', window=10, slope_diff_cutoff=.1, int_diff_cutoff=3, return_df_fit=False):
    if slope_diff_cutoff is None:
        slope_diff_cutoff = np.iinfo(np.int32).max
    if int_diff_cutoff is None:
        int_diff_cutoff = np.iinfo(np.int32).max

    _t_from = '{}_from'.format(t)
    _t_to = '{}_to'.format(t)
    _t_i = '{}_i'.format(t)
    _t_i_from = '{}_i_from'.format(t)
    _t_i_to = '{}_i_to'.format(t)
    _y_slope = '{}_slope'.format(y)
    _y_int = '{}_int'.format(y)
    _y_fit = '{}_fit'.format(y)
    _y_r2 = '{}_r2'.format(y)
    _y_rmse = '{}_rmse'.format(y)

    _df = df[[t, y]].copy().reset_index(drop=True)

    _t_min = _df[t].min()
    _t_max = _df[t].max()

    if isinstance(_df[t].iloc[0], pd.datetime):
        _df[_t_i] = (_df[t] - _t_min) / np.timedelta64(1, t_unit)
        _t_i_min = 0
        _t_i_max = (_df[t].max() - _t_min) / np.timedelta64(1, t_unit)
    else:
        _df[_t_i] = _df[t]
        _t_i_min = _t_min
        _t_i_max = _t_max

    _df['_y'] = (_df[y] - _df[y].mean()) / _df[y].std()

    _df['slope_rolling'] = _df[_t_i].rolling(window, min_periods=0).cov(other=_df['_y'], pairwise=False) / _df[
        _t_i].rolling(window, min_periods=0).var()
    _df['int_rolling'] = _df['_y'].rolling(window, min_periods=0).mean() - _df['slope_rolling'] * _df[_t_i].rolling(
        window, min_periods=0).mean()

    _df['slope_rolling_diff'] = np.abs(_df['slope_rolling'].diff())
    _df['int_rolling_diff'] = np.abs(_df['int_rolling'].diff())

    _df['slope_change'] = _df['slope_rolling_diff'] >= slope_diff_cutoff
    _df['int_change'] = _df['int_rolling_diff'] >= int_diff_cutoff
    _df['_change'] = (_df['slope_change']) | (_df['int_change'])

    _df_phases = _df[_df['_change']][[t, _t_i]]

    _df_phases.insert(0, _t_from, _df_phases[t].shift(1).fillna(_t_min))
    _df_phases.insert(2, _t_i_from, _df_phases[_t_i].shift(1).fillna(_t_i_min))

    _df_phases = _df_phases.rename({t: _t_to, _t_i: _t_i_to}, axis=1)

    # append row for last phase
    _df_phases = _df_phases.append(
        pd.DataFrame({
            _t_from: _df_phases[_t_from].max(),
            _t_to: _t_max,
            _t_i_from: _df_phases[_t_i_from].max(),
            _t_i_to: _t_i_max,
        }, index=[0]), ignore_index=True, sort=False
    )

    _df_phases[_y_slope] = np.nan
    _df_phases[_y_int] = np.nan
    _df_phases[_y_r2] = np.nan
    _df_phases[_y_rmse] = np.nan
    _df_phases['_keep'] = False

    _dfs = []

    _continue = False
    _t_i_from_row = None

    for _i, _row in _df_phases.iterrows():

        # check len of the phase: if len is less than window days it will be merged with next phase
        _t_i_to_row = _row[_t_i_to]

        if not _continue:
            _t_i_from_row = _row[_t_i_from]

        _df_t = _df[(_df[_t_i] >= _t_i_from_row) & (_df[_t_i] < _t_i_to_row)]

        _len_df_t = _df_t.index.max() - _df_t.index.min() + 1

        if _len_df_t < window:
            _continue = True
            continue
        else:
            _continue = False
            _df_phases['_keep'][_i] = True
            _df_phases[_t_i_from][_i] = _t_i_from_row

        # calculate slope
        _y_slope_i = _df_t[_t_i].cov(other=_df_t[y]) / _df_t[_t_i].var()
        # calculate intercept
        _y_int_i = _df_t[y].mean() - _y_slope_i * _df_t[_t_i].mean()

        # calculate y fit
        _df_t[_y_fit] = _y_int_i + _df_t[_t_i] * _y_slope_i

        _df_phases[_y_slope][_i] = _y_slope_i
        _df_phases[_y_int][_i] = _y_int_i
        _df_phases[_y_r2][_i] = r2_score(_df_t[y], _df_t[_y_fit])
        _df_phases[_y_rmse][_i] = np.sqrt(mean_squared_error(_df_t[y], _df_t[_y_fit]))

        _dfs.append(_df_t)

    _df_fit = pd.concat(_dfs)

    # postprocessing
    _df_phases = _df_phases[_df_phases['_keep']].reset_index(drop=True).drop(['_keep'], axis=1)

    if return_df_fit:
        return _df_fit
    else:
        return _df_phases


def col_to_front(df, cols):
    _cols = force_list(cols)

    return df[_cols + [_ for _ in df.columns if _ not in _cols]]


def lr(df, x, y, groupby=None, t_unit='D', do_print=True):
    # const
    _x_i = '_x_i'
    _y_slope = '{}_slope'.format(y)
    _y_int = '{}_int'.format(y)
    _y_fit = '{}_fit'.format(y)
    _y_error = '{}_error'.format(y)

    # init
    if do_print:
        tprint('init')

    _df = df[np.isfinite(df[x]) & np.isfinite(df[y])]

    if groupby is None:

        _df['_dummy'] = 1
        groupby = ['_dummy']

    elif not is_list_like(groupby):
        groupby = [groupby]

    _df_out = dict_list(
        groupby + [_y_slope, _y_int, 'r2', 'rmse', 'error_mean', 'error_std', 'error_abs_mean', 'error_abs_std'])

    if isinstance(_df[x].iloc[0], pd.datetime):
        _df[_x_i] = (_df[x] - _df[x].min()) / np.timedelta64(1, t_unit)
    else:
        _df[_x_i] = _df[x]

    # loop groups

    _i = 0
    _i_max = _df[groupby].drop_duplicates().shape[0]

    for _index, _df_i in _df.groupby(groupby):

        _i += 1

        if do_print:
            tprint('Linear Regression Iteration {} / {}'.format(_i, _i_max))

        _slope = _df_i[_x_i].cov(other=_df_i[y]) / _df_i[_x_i].var()
        _int = _df_i[y].mean() - _slope * _df_i[_x_i].mean()
        _df_i[_y_fit] = _slope * _df_i[x] + _int
        _df_i[_y_error] = _df_i[_y_fit] - _df_i[y]

        _r2 = r2(_df_i[y], _df_i[_y_fit])
        _rmse = rmse(_df_i[y], _df_i[_y_fit])

        append_to_dict_list(_df_out, _index)
        append_to_dict_list(_df_out, {
            _y_slope: _slope,
            _y_int: _int,
            'r2': _r2,
            'rmse': _rmse,
            'error_mean': _df_i[_y_error].mean(),
            'error_std': _df_i[_y_error].std(),
            'error_abs_mean': _df_i[_y_error].abs().mean(),
            'error_abs_std': _df_i[_y_error].abs().std()
        })

    _df_out = pd.DataFrame(_df_out)

    if '_dummy' in _df_out.columns:
        _df_out = _df_out.drop(['_dummy'], axis=1)

    if do_print:
        tprint('Linear Regression done')

    return _df_out


def flatten(lst):
    # https://stackoverflow.com/questions/952914/how-to-make-a-flat-list-out-of-list-of-lists

    def _flatten_generator(_lst):

        for _x in _lst:
            if is_list_like(_x):
                for _sub_x in flatten(_x):
                    yield _sub_x
            else:
                yield _x

    return list(_flatten_generator(lst))


@export
def df_split(df: pd.DataFrame, split_by: Union[List[str], str], return_type: str = 'dict', print_key: bool = False,
             sep: str = '_', key_sep: str = '==') -> Union[list, dict]:
    """
    Split a pandas DataFrame by column value and returns a list or dict

    :param df: pandas DataFrame to be split
    :param split_by: Column(s) to split by, creates a sub-DataFrame for each level
    :param return_type: one of ['list', 'dict'], if list returns a list of sub-DataFrame, if dict returns a dictionary
        with each level as keys
    :param print_key: whether to include the column names in the key labels
    :param sep: separator to use in the key labels between columns
    :param key_sep: separator to use in the key labels between key and value
    :return: see return_type
    """

    _split_by = force_list(split_by)

    if return_type == 'list':
        _dfs = []
    else:
        _dfs = {}

    for _i, _df in df.groupby(_split_by):

        if return_type == 'list':
            _dfs.append(_df)
        else:
            _key = qformat(pd.DataFrame(_df[_split_by]).head(1), print_key=print_key, sep=sep, key_sep=key_sep)
            _dfs[_key] = _df

    return _dfs


# merges a df, wrapper for pd.concat
def df_merge(*args, ignore_index=True, sort=False, **kwargs):
    return pd.concat(*args, ignore_index=ignore_index, sort=sort, **kwargs)


def rank(df, rank_by, groupby=None, score_ascending=True, sort_by=None, sort_by_ascending=None):
    if sort_by is None:
        sort_by = []
    _df = df.copy()
    del df

    if groupby is None:
        groupby = ['_dummy']
        _df['_dummy'] = 1

    _sort_by = force_list(rank_by) + force_list(groupby) + force_list(sort_by)

    _df['_row'] = _df.assign(_row=1)['_row'].cumsum()

    if sort_by_ascending is None:
        _ascending = score_ascending
    else:
        _ascending = force_list(score_ascending) + [True for _ in groupby] + force_list(sort_by_ascending)

    _df = _df.sort_values(by=_sort_by, ascending=_ascending).assign(rank=1)
    _df['_rank'] = _df.groupby(groupby)['rank'].cumsum()
    _df = _df.sort_values(by='_row')

    return _df['_rank']


def kde(x, df=None, x_range=None, perc_cutoff=.1, range_cutoff=None, x_steps=1000):
    if df is not None:

        _df = df.copy()
        del df

        if x in ['value', 'perc', 'diff', 'sign', 'ex', 'ex_max', 'ex_min', 'mean', 'std', 'range',
                 'value_min', 'value_max', 'range_min', 'range_max']:
            raise ValueError('x cannot be named {}, please rename your variable'.format(x))
    else:
        _df = None

    # std cutoff = norm(0,1).pdf(1)/norm(0,1).pdf(0)
    # 1/e cutoff: range_cutoff = 1-1/e = .63
    # full width at half maximum: range_cutoff = .5
    if range_cutoff is None or range_cutoff in ['sigma', 'std']:
        _range_cutoff = stats.norm(0, 1).pdf(1) / stats.norm(0, 1).pdf(0)
    elif range_cutoff in ['e', '1/e', '1-1/e']:
        _range_cutoff = 1 - 1 / np.exp(1)
    elif range_cutoff in ['fwhm', 'FWHM', 'hm', 'HM']:
        _range_cutoff = .5
    else:
        _range_cutoff = range_cutoff + 0

    if _df is not None:
        _x = _df[x]
        _x_name = x
    else:
        _x = x
        if 'name' in dir(x):
            _x_name = x.name
        else:
            _x_name = 'x'

    assert(len(_x) > 0), 'Series {} has zero length'.format(_x_name)
    _x = pd.Series(_x).reset_index(drop=True)

    _x_name_max = _x_name + '_max'

    if x_range is None:
        x_range = np.linspace(np.nanmin(_x), np.nanmax(_x), x_steps)

    # -- fit kde
    _kde = stats.gaussian_kde(_x)

    # -- to df
    _df_kde = pd.DataFrame({_x_name: x_range, 'value': _kde.evaluate(x_range)})
    _df_kde['perc'] = _df_kde['value'] / _df_kde['value'].max()

    # -- get extrema
    _df_kde['diff'] = _df_kde['value'].diff()
    _df_kde['sign'] = np.sign(_df_kde['diff'])
    _df_kde['ex_max'] = _df_kde['sign'].diff(-1).fillna(0) > 0
    _df_kde['ex_min'] = _df_kde['sign'].diff(-1).fillna(0) < 0
    _df_kde['phase'] = _df_kde['ex_min'].astype(int).cumsum()

    if perc_cutoff:
        _df_kde['ex_max'] = _df_kde['ex_max'].where(_df_kde['perc'] > perc_cutoff, False)

    # -- get std
    # we get the extrema and do a full merge to find the closest one to each point
    _df_kde_ex = _df_kde.query('ex_max')[[_x_name, 'value', 'phase']].reset_index()
    _df_kde_ex['mean'] = np.nan
    _df_kde_ex['std'] = np.nan
    _df_kde_ex['range'] = np.nan
    _df_kde_ex['range_min'] = np.nan
    _df_kde_ex['range_max'] = np.nan
    _df_kde_ex['value_min'] = np.nan
    _df_kde_ex['value_max'] = np.nan

    for _index, _row in _df_kde_ex.iterrows():
        _df_kde_i = _df_kde[_df_kde['phase'] == _row['phase']]

        # Width of Peak range
        _df_kde_i = _df_kde_i[_df_kde_i['value'] >= _row['value'] * _range_cutoff]

        _x_min = _df_kde_i[_x_name].iloc[0]
        _x_max = _df_kde_i[_x_name].iloc[-1]

        _x_i = np.extract((_x > _x_min) & (_x < _x_max), _x)

        _mean, _std = stats.norm.fit(_x_i)

        _df_kde_ex['mean'].loc[_index] = _mean
        _df_kde_ex['std'].loc[_index] = _std

        _df_kde_ex['range'].loc[_index] = _x_max - _x_min
        _df_kde_ex['range_min'].loc[_index] = _x_min
        _df_kde_ex['range_max'].loc[_index] = _x_max
        _df_kde_ex['value_min'].loc[_index] = _df_kde_i['value'].iloc[0]
        _df_kde_ex['value_max'].loc[_index] = _df_kde_i['value'].iloc[-1]

    return _df_kde, _df_kde_ex


# wrapper to quickly aggregate df
def qagg(df: pd.DataFrame, groupby, columns=None, agg=None, reset_index=True):
    if agg is None:
        agg = ['mean', 'std']
    if columns is None:
        columns = df.select_dtypes(include=np.number).columns

    _df_agg = df.groupby(groupby).agg({_: agg for _ in columns})
    _df_agg = _df_agg.set_axis(flatten([[_ + '_mean', _ + '_std'] for _ in columns]), axis=1, inplace=False)
    if reset_index:
        _df_agg = _df_agg.reset_index()
    return _df_agg


@export
def mahalanobis(point: Union[pd.DataFrame, pd.Series, np.ndarray], df: pd.DataFrame = None, params: List[str] = None,
                do_print: bool = True) -> Union[float, List[float]]:
    """
    Calculates the Mahalanobis distance for a single point or a DataFrame of points

    :param point: The point(s) to calculate the Mahalanobis distance for
    :param df: The reference DataFrame against which to calculate the Mahalanobis distance
    :param params: The columns to calculate the Mahalanobis distance for
    :param do_print: Whether to print intermediate steps to the console
    :return: if a single point is passed: Mahalanobis distance as float, else a list of floats
    """
    if df is None:
        df = point

    _df = df.copy()
    del df

    if params is None:
        params = _df.columns
    else:
        _df = _df[params]

    try:
        _vi = np.linalg.inv(_df.cov())
    except np.linalg.LinAlgError:
        return np.nan

    _y = _df.mean().values

    if isinstance(point, pd.DataFrame):

        _out = []

        _it = -1
        for _index, _row in point.iterrows():

            _it += 1

            if do_print:
                progressbar(_it, point.shape[0])

            _x = _row[params].values
            _out.append(distance.mahalanobis(_x, _y, _vi))

        if do_print:
            progressbar()
        return _out

    elif isinstance(point, pd.Series):
        _x = point[params].values
    else:
        _x = np.array(point)

    return distance.mahalanobis(_x, _y, _vi)


def multi_melt(df, cols, suffixes, id_vars, var_name='variable', sep='_', **kwargs):
    # for multi melt to work the columns must share common suffixes

    _df = df.copy()
    del df

    _df_out = []

    for _col in cols:
        _value_vars = ['{}{}{}'.format(_col, sep, _suffix) for _suffix in suffixes]

        _df_out_i = _df.melt(id_vars=id_vars, value_vars=_value_vars, value_name=_col, var_name=var_name, **kwargs)
        _df_out_i[var_name] = _df_out_i[var_name].str.slice(len(_col) + len(sep))
        _df_out_i = _df_out_i.sort_values(by=force_list(id_vars) + [var_name]).reset_index(drop=True)
        _df_out.append(_df_out_i)

    _df_out = pd.concat(_df_out, axis=1).pipe(drop_duplicate_cols)

    return _df_out


# for resampling integer indexes
def resample(df, rule=1, on=None, groupby=None, agg='mean', columns=None, adj_column_names=True, factor=1, **kwargs):
    assert isinstance(df, pd.DataFrame), 'df must be a DataFrame'

    _df = df.copy()
    del df

    if on is not None:
        _df = _df.set_index(on)
    if columns is None:
        _columns = _df.select_dtypes(include=np.number).columns
    else:
        _columns = columns
    if groupby is not None:
        _columns = [_ for _ in _columns if _ not in force_list(groupby)]
        _df = _df.groupby(groupby)

    # convert int to seconds to be able to use .resample
    _df.index = pd.to_datetime(_df.index * factor, unit='s')

    # resample as time series
    _df = _df.resample('{}s'.format(rule), **kwargs)

    # agg
    _adj_column_names = False
    if agg == 'mean':
        _df = _df.mean()
    elif agg == 'median':
        _df = _df.median()
    elif agg == 'sum':
        _df = _df.sum()
    else:
        _df = _df.agg({_: agg for _ in _columns})
        if adj_column_names:
            _adj_column_names = True

    # back to int
    _df.index = ((_df.index - pd.to_datetime('1970-01-01')).total_seconds() / factor)
    if _adj_column_names:
        _column_names = []
        for _col in _columns:
            for _agg in force_list(agg):
                _column_names += ['{}_{}'.format(_col, _agg)]
        _df.columns = _column_names

    return _df


def df_count(x, df, hue=None, sort_by_count=True, top_nr=5, x_int=None, x_min=None, x_max=None, other_name='other',
             na='drop'):
    # -- init
    _df = df.copy()
    del df

    if na != 'drop':
        _df[x] = _df[x].astype(str).fillna('NaN')
        if hue is not None: 
            _df[hue] = _df[hue].astype(str).fillna('NaN')

    if not top_nr: 
        top_nr = None

    if x == 'count':
        x = 'count_org'
        _df = _df.rename({'count': 'count_org'}, axis=1)

    # -- preprocessing
    if x_int is not None:

        _df[x] = np.round(_df[x] / x_int) * x_int
        if isinstance(x_int, int): 
            _df[x] = _df[x].astype(int)

        if x_min is None: 
            x_min = _df[x].min()
        if x_max is None: 
            x_max = _df[x].max()

        _df_xs = pd.DataFrame({x: range(x_min, x_max, x_int)})
        _xs_on = [x]

        if hue is not None:
            _df_hues = _df[[hue]].drop_duplicates().reset_index().assign(_dummy=1)
            _df_xs = pd.merge(_df_xs.assign(_dummy=1), _df_hues, on='_dummy').drop(['_dummy'], axis=1)
            _xs_on = _xs_on + [hue]
            
    else:
        _df_xs = pd.DataFrame()
        _xs_on = []

    # dummy
    _df['_count'] = 1

    # group values outside of top_n to other_name
    if top_nr is not None:

        _df[x] = top_n_coding(s=_df[x], n=top_nr, other_name=other_name)

        if hue is not None:
            _df[hue] = top_n_coding(s=_df[hue], n=top_nr, other_name=other_name)

    # init df with counts
    _groupby = [x]
    if hue is not None: 
        _groupby = _groupby + [hue]

    _df_count = _df.groupby(_groupby).agg({'_count': 'sum'}).reset_index().rename({'_count': 'count'}, axis=1)

    # append 0 entries for numerical x
    if x_int is not None:
        _df_count = pd.merge(_df_count, _df_xs, on=_xs_on, how='outer')
        _df_count['count'] = _df_count['count'].fillna(0)

    # create total count (for perc)
    _count_x = 'count_{}'.format(x)
    _count_hue = 'count_{}'.format(hue)

    if hue is None:
        _df_count[_count_hue] = _df_count['count'].sum()
        _df_count[_count_x] = _df_count['count']
    else:

        _df_count[_count_x] = _df_count.groupby(x)['count'].transform(pd.Series.sum)
        _df_count[_count_hue] = _df_count.groupby(hue)['count'].transform(pd.Series.sum)

    # sort
    if sort_by_count: 
        _df_count = _df_count.sort_values([_count_x], ascending=False).reset_index(drop=True)

    _df_count['perc_{}'.format(x)] = np.round(_df_count['count'] / _df_count[_count_x] * 100, 2)
    _df_count['perc_{}'.format(hue)] = np.round(_df_count['count'] / _df_count[_count_hue] * 100, 2)

    return _df_count


# return prediction accuracy in percent
def get_accuracy(class_true, class_pred):
    return np.where(class_true.astype(str) == class_pred.astype(str), 1, 0).sum() / len(class_true)


# takes a numeric pandas series and splits it into groups, the groups are labeled by INTEGER multiples of the step value
def numeric_to_group(pd_series, step=None, outer_limit=4, suffix=None, use_abs=False, use_standard_scaler=True):
    # outer limit is given in steps, only INTEGER values allowed
    outer_limit = int(outer_limit)

    # make a copy to avoid inplace effects
    _series = pd.Series(deepcopy(pd_series))

    # use standard scaler to center around mean with std +- 1
    if use_standard_scaler: 
        _series = StandardScaler().fit(_series.values.reshape(-1, 1)).transform(_series.values.reshape(-1, 1)).flatten()

    # if step is none: use 1 as step
    if step is None: 
        step = 1
    if suffix is None:
        if use_standard_scaler:
            suffix = 'std'
        else:
            suffix = 'step'

    if suffix != '': 
        suffix = '_' + suffix

    # to absolute
    if use_abs:
        _series = np.abs(_series)
    else:
        # gather the +0 and -0 group to 0
        _series = np.where(np.abs(_series) < step, 0, _series)

    # group

    # get sign
    _series_sign = np.sign(_series)

    # divide by step, floor and integer
    _series = (np.floor(np.abs(_series) / step)).astype(int) * np.sign(_series).astype(int)

    # apply outer limit
    if outer_limit is not None:
        _series = np.where(_series > outer_limit, outer_limit, _series)
        _series = np.where(_series < -outer_limit, -outer_limit, _series)

    # make a pretty string
    _series = pd.Series(_series).apply(lambda x: '{0:n}'.format(x)).astype('str') + suffix

    # to cat
    _series = _series.astype('category')

    return _series


# select n elements form a categorical pandas series with the highest counts
def top_n(s: pd.Series, n: int) -> list:
    return list(s.value_counts().reset_index()['index'][:n])


# returns a modified version of the pandas series where all elements not in top_n become recoded as 'other'
def top_n_coding(s, n, other_name='other', na_to_other=False):
    _s = s.astype('str')
    _top_n = top_n(_s, n)

    _s = pd.Series(np.where(_s.isin(_top_n), _s, other_name))

    if na_to_other: 
        _s = pd.Series(np.where(~_s.isin(['nan', 'nat']), _s, other_name))

    _s = pd.Series(_s)

    # get back the old properties of the series (or you'll screw the index)
    _s.name = s.name
    _s.index = s.index

    # convert to cat
    _s = _s.astype('category')

    return _s


@export
def k_split(df: pd.DataFrame, k: int = 5, groupby: Union[Sequence, str] = None,
            sortby: Union[Sequence, str] = None, random_state: int = None, do_print: bool = True,
            return_type: Union[str, int] = 1) -> Union[pd.Series, tuple]:
    """
    splits a DataFrame into k (equal sized) parts that can be used for train test splitting or k_cross splitting

    :param df: pandas DataFrame to be split
    :param k: how many (equal sized) parts to split the DataFrame into [optional]
    :param groupby: passed to pandas.DataFrame.groupby before splitting,
        ensures that each group will be represented equally in each split part [optional]
    :param sortby: if True the DataFrame is ordered by these column(s) and then sliced into parts from the top
        if False the DataFrame is sorted randomly before slicing [optional]
    :param random_state: random_state to be used in random sorting, ignore if sortby is True [optional]
    :param do_print: whether to print steps to console [optional]
    :param return_type: if one of ['Series', 's'] returns a pandas Series containing the k indices range(k)
        if a positive integer < k returns tuple of shape (df_train, df_test) where the return_type'th part
        is equal to df_test and the other parts are equal to df_train
    :return: depending on return_type either a pandas Series or a tuple
    """

    if do_print:
        tprint('splitting 1:{} ...'.format(k))

    # -- init
    _df = df.copy()
    del df

    _index_name = _df.index.name
    _df['_index'] = _df.index.copy()
    _df = _df.reset_index(drop=True)
    _k_split = int(np.ceil(_df.shape[0] / k))

    if groupby is None:
        groupby = '_dummy'
        _df['_dummy'] = 1

    _df_out = []

    for _index, _df_i in _df.groupby(groupby):

        # sort (randomly or by given value)
        if sortby is None:
            _df_i = _df_i.sample(frac=1, random_state=random_state).reset_index(drop=True)
        else:
            if sortby == 'index':
                _df_i = _df_i.sort_index()
            else:
                _df_i = _df_i.sort_values(by=sortby).reset_index(drop=True)

        # assign k index
        _df_i['_k_index'] = _df_i.index // _k_split

        _df_out.append(_df_i)

    _df_out = df_merge(_df_out).set_index(['_index']).sort_index()
    _df_out.index = _df_out.index.rename(None)

    if '_dummy' in _df_out.columns:
        _df_out = _df_out.drop(['_dummy'], axis=1)

    if return_type in range(k):
        _df_train = _df_out[_df_out['_k_index'] != return_type].drop('_k_index', axis=1)
        _df_test = _df_out[_df_out['_k_index'] == return_type].drop('_k_index', axis=1)
        return _df_train, _df_test
    else:
        return _df_out['_k_index']