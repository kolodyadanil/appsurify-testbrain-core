import numpy as np


class Statistic(object):
    _context = {}

    _current = 0
    _total = 0
    _success = 0
    _failure = 0

    def __str__(self):
        return f"[{self._current}/{self._total}] ({self._success}/{self._failure})"

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, value):
        self._context = value

    @property
    def progress_percent(self):
        if self._total == 0:
            return 0
        return self._current * 100 // self._total

    @property
    def progress_percent_float(self):
        if self._total == 0:
            return 0
        return self._current * 100 / self._total

    @property
    def total(self):
        return self._total

    @total.setter
    def total(self, value):
        self._total = value

    @property
    def current(self):
        return self._current

    @property
    def success(self):
        return self._success

    @property
    def failure(self):
        return self._failure

    def increase_current(self):
        self._current += 1

    def increase_success(self):
        self._success += 1

    def increase_failure(self):
        self._failure += 1

    def reset(self):
        self._total = 0
        self._current = 0
        self._success = 0
        self._failure = 0

def reduce_mem_usage(df):
    """ iterate through all the columns of a dataframe and modify the data type
        to reduce memory usage.
    """
    start_mem = df.memory_usage().sum() / 1024
    # print('Memory usage of dataframe is {:.2f} KB'.format(start_mem))

    for col in df.columns:
        col_type = df[col].dtype

        if col_type != object and col_type.name != 'category' and 'datetime' not in col_type.name:
            c_min = df[col].min()
            c_max = df[col].max()
            if str(col_type)[:3] == 'int':
                if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                    df[col] = df[col].astype(np.int8)
                elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                    df[col] = df[col].astype(np.int16)
                elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                    df[col] = df[col].astype(np.int32)
                elif c_min > np.iinfo(np.int64).min and c_max < np.iinfo(np.int64).max:
                    df[col] = df[col].astype(np.int64)
            else:
                if c_min > np.finfo(np.float16).min and c_max < np.finfo(np.float16).max:
                    df[col] = df[col].astype(np.float16)
                elif c_min > np.finfo(np.float32).min and c_max < np.finfo(np.float32).max:
                    df[col] = df[col].astype(np.float32)
                else:
                    df[col] = df[col].astype(np.float64)
        elif 'datetime' not in col_type.name:
            df[col] = df[col].astype('category')

    end_mem = df.memory_usage().sum() / 1024
    # print('Memory usage after optimization is: {:.2f} KB'.format(end_mem))
    # print('Decreased by {:.1f}%'.format(100 * (start_mem - end_mem) / start_mem))

    return df
