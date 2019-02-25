import unittest
import warnings
from itertools import chain
from functools import partial, wraps

import numpy as np
from scipy.sparse import csr_matrix, issparse, lil_matrix, csc_matrix, \
    SparseEfficiencyWarning

from Orange.statistics.util import bincount, countnans, contingency, digitize, \
    mean, nanmax, nanmean, nanmedian, nanmin, nansum, nanunique, stats, std, \
    unique, var, nanstd, nanvar, nanmode, array_equal, FDR
from sklearn.utils import check_random_state


def dense_sparse(test_case):
    # type: (Callable) -> Callable
    """Run a single test case on both dense and sparse data."""
    @wraps(test_case)
    def _wrapper(self):

        def sparse_with_explicit_zero(x, array):
            """Inject one explicit zero into a sparse array."""
            np_array, sp_array = np.atleast_2d(x), array(x)
            assert issparse(sp_array), 'Can not inject explicit zero into non-sparse matrix'

            zero_indices = np.argwhere(np_array == 0)
            if zero_indices.size:
                with warnings.catch_warnings():
                    # this is just inefficiency in tests, not the tested code
                    warnings.filterwarnings("ignore", ".*",
                                            SparseEfficiencyWarning)
                    sp_array[tuple(zero_indices[0])] = 0

            return sp_array

        test_case(self, np.array)
        test_case(self, csr_matrix)
        test_case(self, csc_matrix)
        test_case(self, partial(sparse_with_explicit_zero, array=csr_matrix))
        test_case(self, partial(sparse_with_explicit_zero, array=csc_matrix))

    return _wrapper


class TestUtil(unittest.TestCase):
    def setUp(self):
        nan = float('nan')
        self.data = [
            np.array([
                [0., 1., 0., nan, 3., 5.],
                [0., 0., nan, nan, 5., nan],
                [0., 0., 0., nan, 7., 6.]]),
            np.zeros((2, 3)),
            np.ones((2, 3)),
        ]

    def test_contingency(self):
        x = np.array([0, 1, 0, 2, np.nan])
        y = np.array([0, 0, 1, np.nan, 0])
        cont_table, nans = contingency(x, y, 2, 2)
        np.testing.assert_equal(cont_table, [[1, 1, 0],
                                             [1, 0, 0],
                                             [0, 0, 0]])
        np.testing.assert_equal(nans, [1, 0, 0])

    def test_weighted_contingency(self):
        x = np.array([0, 1, 0, 2, np.nan])
        y = np.array([0, 0, 1, np.nan, 0])
        w = np.array([1, 2, 2, 3, 4])
        cont_table, nans = contingency(x, y, 2, 2, weights=w)
        np.testing.assert_equal(cont_table, [[1, 2, 0],
                                             [2, 0, 0],
                                             [0, 0, 0]])
        np.testing.assert_equal(nans, [1, 0, 0])

    def test_stats(self):
        X = np.arange(4).reshape(2, 2).astype(float)
        X[1, 1] = np.nan
        np.testing.assert_equal(stats(X), [[0, 2, 1, 0, 0, 2],
                                           [1, 1, 1, 0, 1, 1]])
        # empty table should return ~like metas
        X = X[:0]
        np.testing.assert_equal(stats(X), [[np.inf, -np.inf, 0, 0, 0, 0],
                                           [np.inf, -np.inf, 0, 0, 0, 0]])

    def test_stats_sparse(self):
        X = csr_matrix(np.identity(5))
        np.testing.assert_equal(stats(X), [[0, 1, .2, 0, 4, 1],
                                           [0, 1, .2, 0, 4, 1],
                                           [0, 1, .2, 0, 4, 1],
                                           [0, 1, .2, 0, 4, 1],
                                           [0, 1, .2, 0, 4, 1]])

        # assure last two columns have just zero elements
        X = X[:3]
        np.testing.assert_equal(stats(X), [[0, 1, 1/3, 0, 2, 1],
                                           [0, 1, 1/3, 0, 2, 1],
                                           [0, 1, 1/3, 0, 2, 1],
                                           [0, 0, 0, 0, 3, 0],
                                           [0, 0, 0, 0, 3, 0]])

    def test_stats_weights(self):
        X = np.arange(4).reshape(2, 2).astype(float)
        weights = np.array([1, 3])
        np.testing.assert_equal(stats(X, weights), [[0, 2, 1.5, 0, 0, 2],
                                                    [1, 3, 2.5, 0, 0, 2]])

        X = np.arange(4).reshape(2, 2).astype(object)
        np.testing.assert_equal(stats(X, weights), stats(X))

    def test_stats_weights_sparse(self):
        X = np.arange(4).reshape(2, 2).astype(float)
        X = csr_matrix(X)
        weights = np.array([1, 3])
        np.testing.assert_equal(stats(X, weights), [[0, 2, 1.5, 0, 1, 1],
                                                    [1, 3, 2.5, 0, 0, 2]])

    def test_stats_non_numeric(self):
        X = np.array([
            ['', 'a', 'b'],
            ['a', '', 'b'],
            ['a', 'b', ''],
        ], dtype=object)
        np.testing.assert_equal(stats(X), [[np.inf, -np.inf, 0, 0, 1, 2],
                                           [np.inf, -np.inf, 0, 0, 1, 2],
                                           [np.inf, -np.inf, 0, 0, 1, 2]])

    def test_nanmin_nanmax(self):
        warnings.filterwarnings("ignore", r".*All-NaN slice encountered.*")
        for X in self.data:
            X_sparse = csr_matrix(X)
            for axis in [None, 0, 1]:
                np.testing.assert_array_equal(
                    nanmin(X, axis=axis),
                    np.nanmin(X, axis=axis))

                np.testing.assert_array_equal(
                    nanmin(X_sparse, axis=axis),
                    np.nanmin(X, axis=axis))

                np.testing.assert_array_equal(
                    nanmax(X, axis=axis),
                    np.nanmax(X, axis=axis))

                np.testing.assert_array_equal(
                    nanmax(X_sparse, axis=axis),
                    np.nanmax(X, axis=axis))

    @dense_sparse
    def test_nansum(self, array):
        for X in self.data:
            X_sparse = array(X)
            np.testing.assert_array_equal(
                nansum(X_sparse),
                np.nansum(X))

    def test_mean(self):
        # This warning is not unexpected and it's correct
        warnings.filterwarnings("ignore", r".*mean\(\) resulted in nan.*")
        for X in self.data:
            X_sparse = csr_matrix(X)
            np.testing.assert_array_equal(
                mean(X_sparse),
                np.mean(X))

        with self.assertWarns(UserWarning):
            mean([1, np.nan, 0])

    def test_nanmode(self):
        X = np.array([[np.nan, np.nan, 1, 1],
                      [2, np.nan, 1, 1]])
        mode, count = nanmode(X, 0)
        np.testing.assert_array_equal(mode, [[2, np.nan, 1, 1]])
        np.testing.assert_array_equal(count, [[1, np.nan, 2, 2]])
        mode, count = nanmode(X, 1)
        np.testing.assert_array_equal(mode, [[1], [1]])
        np.testing.assert_array_equal(count, [[2], [2]])

    @dense_sparse
    def test_nanmedian(self, array):
        for X in self.data:
            X_sparse = array(X)
            np.testing.assert_array_equal(
                nanmedian(X_sparse),
                np.nanmedian(X))

    @dense_sparse
    def test_nanmedian_more_nonzeros(self, array):
        X = np.ones((10, 10))
        X[:5, 0] = np.nan
        X[:6, 1] = 0
        X_sparse = array(X)
        np.testing.assert_array_equal(
            nanmedian(X_sparse),
            np.nanmedian(X)
        )

    def test_var(self):
        for data in self.data:
            for axis in chain((None,), range(len(data.shape))):
                # Can't use array_equal here due to differences on 1e-16 level
                np.testing.assert_array_almost_equal(
                    var(csr_matrix(data), axis=axis),
                    np.var(data, axis=axis)
                )

    def test_var_with_ddof(self):
        x = np.random.uniform(0, 10, (20, 100))
        for axis in [None, 0, 1]:
            np.testing.assert_almost_equal(
                np.var(x, axis=axis, ddof=10),
                var(csr_matrix(x), axis=axis, ddof=10),
            )

    @dense_sparse
    def test_nanvar(self, array):
        for X in self.data:
            X_sparse = array(X)
            np.testing.assert_array_equal(
                nanvar(X_sparse),
                np.nanvar(X))

    def test_nanvar_with_ddof(self):
        x = np.random.uniform(0, 10, (20, 100))
        np.fill_diagonal(x, np.nan)
        for axis in [None, 0, 1]:
            np.testing.assert_almost_equal(
                np.nanvar(x, axis=axis, ddof=10),
                nanvar(csr_matrix(x), axis=axis, ddof=10),
            )

    def test_std(self):
        for data in self.data:
            for axis in chain((None,), range(len(data.shape))):
                # Can't use array_equal here due to differences on 1e-16 level
                np.testing.assert_array_almost_equal(
                    std(csr_matrix(data), axis=axis),
                    np.std(data, axis=axis)
                )

    def test_std_with_ddof(self):
        x = np.random.uniform(0, 10, (20, 100))
        for axis in [None, 0, 1]:
            np.testing.assert_almost_equal(
                np.std(x, axis=axis, ddof=10),
                std(csr_matrix(x), axis=axis, ddof=10),
            )

    @dense_sparse
    def test_nanstd(self, array):
        for X in self.data:
            X_sparse = array(X)
            np.testing.assert_array_equal(
                nanstd(X_sparse),
                np.nanstd(X))

    def test_nanstd_with_ddof(self):
        x = np.random.uniform(0, 10, (20, 100))
        for axis in [None, 0, 1]:
            np.testing.assert_almost_equal(
                np.nanstd(x, axis=axis, ddof=10),
                nanstd(csr_matrix(x), axis=axis, ddof=10),
            )

    def test_FDR(self):
        p_values = np.array([0.0002, 0.0004, 0.00001, 0.0003, 0.0001])
        np.testing.assert_almost_equal(
            np.array([0.00033, 0.0004, 0.00005, 0.00038, 0.00025]),
            FDR(p_values), decimal=5)

    def test_FDR_dependent(self):
        p_values = np.array([0.0002, 0.0004, 0.00001, 0.0003, 0.0001])
        np.testing.assert_almost_equal(
            np.array([0.00076, 0.00091, 0.00011, 0.00086, 0.00057]),
            FDR(p_values, dependent=True), decimal=5)

    def test_FDR_m(self):
        p_values = np.array([0.0002, 0.0004, 0.00001, 0.0003, 0.0001])
        np.testing.assert_almost_equal(
            np.array([0.0002, 0.00024, 0.00003, 0.000225, 0.00015]),
            FDR(p_values, m=3), decimal=5)

    def test_FDR_no_values(self):
        self.assertIsNone(FDR(None))
        self.assertIsNone(FDR([]))
        self.assertIsNone(FDR([0.0002, 0.0004], m=0))

    def test_FDR_list(self):
        p_values = [0.0002, 0.0004, 0.00001, 0.0003, 0.0001]
        result = FDR(p_values)
        self.assertIsInstance(result, list)
        np.testing.assert_almost_equal(
            np.array([0.00033, 0.0004, 0.00005, 0.00038, 0.00025]),
            result, decimal=5)


class TestNanmean(unittest.TestCase):
    def setUp(self):
        self.random_state = check_random_state(42)
        self.x = self.random_state.uniform(size=(10, 5))
        np.fill_diagonal(self.x, np.nan)

    @dense_sparse
    def test_axis_none(self, array):
        np.testing.assert_almost_equal(
            np.nanmean(self.x), nanmean(array(self.x))
        )

    @dense_sparse
    def test_axis_0(self, array):
        np.testing.assert_almost_equal(
            np.nanmean(self.x, axis=0), nanmean(array(self.x), axis=0)
        )

    @dense_sparse
    def test_axis_1(self, array):
        np.testing.assert_almost_equal(
            np.nanmean(self.x, axis=1), nanmean(array(self.x), axis=1)
        )


class TestDigitize(unittest.TestCase):
    def setUp(self):
        # pylint: disable=bad-whitespace
        self.data = [
            np.array([
                [0., 1.,     0., np.nan, 3.,     5.],
                [0., 0., np.nan, np.nan, 5., np.nan],
                [0., 0.,     0., np.nan, 7.,     6.]]),
            np.zeros((2, 3)),
            np.ones((2, 3)),
        ]

    @dense_sparse
    def test_digitize(self, array):
        for x_original in self.data:
            x = array(x_original)
            bins = np.arange(-2, 2)

            x_shape = x.shape
            np.testing.assert_array_equal(
                np.digitize(x_original.flatten(), bins).reshape(x_shape),
                digitize(x, bins),
            )

    @dense_sparse
    def test_digitize_right(self, array):
        for x_original in self.data:
            x = array(x_original)
            bins = np.arange(-2, 2)

            x_shape = x.shape
            np.testing.assert_array_equal(
                np.digitize(x_original.flatten(), bins, right=True).reshape(x_shape),
                digitize(x, bins, right=True)
            )

    @dense_sparse
    def test_digitize_1d_array(self, array):
        """A consistent return shape must be returned for both sparse and dense."""
        x_original = np.array([0, 1, 1, 0, np.nan, 0, 1])
        x = array(x_original)
        bins = np.arange(-2, 2)

        x_shape = x_original.shape
        np.testing.assert_array_equal(
            [np.digitize(x_original.flatten(), bins).reshape(x_shape)],
            digitize(x, bins),
        )

    def test_digitize_sparse_zeroth_bin(self):
        # Setup the data so that the '0's will fit into the '0'th bin.
        data = csr_matrix([
            [0, 0, 0, 1, 1, 0, 0, 1, 0],
            [0, 0, 1, 1, 0, 0, 1, 0, 0],
        ])
        bins = np.array([1])
        # Then digitize should return a sparse matrix
        self.assertTrue(issparse(digitize(data, bins)))


class TestCountnans(unittest.TestCase):
    @dense_sparse
    def test_1d_array(self, array):
        x = array([0, 1, 0, 2, 2, np.nan, 1, np.nan, 0, 1])
        self.assertEqual(countnans(x), 2)

    @dense_sparse
    def test_1d_array_with_axis_0(self, array):
        x = array([0, 1, 0, 2, 2, np.nan, 1, np.nan, 0, 1])
        expected = 2

        self.assertEqual(countnans(x, axis=0), expected)

    @dense_sparse
    def test_1d_array_with_axis_1_raises_exception(self, array):
        with self.assertRaises(ValueError):
            countnans(array([0, 1, 0, 2, 2, np.nan, 1, np.nan, 0, 1]), axis=1)

    @dense_sparse
    def test_shape_matches_dense_and_sparse(self, array):
        x = array([[0, 1, 0, 2, 2, np.nan, 1, np.nan, 0, 1],
                   [1, 2, 2, 1, np.nan, 1, 2, 3, np.nan, 3]])
        expected = 4

        self.assertEqual(countnans(x), expected)

    @dense_sparse
    def test_shape_matches_dense_and_sparse_with_axis_0(self, array):
        x = array([[0, 1, 0, 2, 2, np.nan, 1, np.nan, 0, 1],
                   [1, 2, 2, 1, np.nan, 1, 2, np.nan, 3, 3]])
        expected = [0, 0, 0, 0, 1, 1, 0, 2, 0, 0]

        np.testing.assert_equal(countnans(x, axis=0), expected)

    @dense_sparse
    def test_shape_matches_dense_and_sparse_with_axis_1(self, array):
        x = array([[0, 1, 0, 2, 2, np.nan, 1, np.nan, 0, 1],
                   [1, 2, 2, 1, np.nan, 1, 2, 3, np.nan, 3]])
        expected = [2, 2]

        np.testing.assert_equal(countnans(x, axis=1), expected)

    @dense_sparse
    def test_2d_matrix(self, array):
        x = array([[1, np.nan, 1, 2],
                   [2, np.nan, 2, 3]])
        expected = 2

        self.assertEqual(countnans(x), expected)

    @dense_sparse
    def test_on_columns(self, array):
        x = array([[1, np.nan, 1, 2],
                   [2, np.nan, 2, 3]])
        expected = [0, 2, 0, 0]

        np.testing.assert_equal(countnans(x, axis=0), expected)

    @dense_sparse
    def test_on_rows(self, array):
        x = array([[1, np.nan, 1, 2],
                   [2, np.nan, 2, 3]])
        expected = [1, 1]

        np.testing.assert_equal(countnans(x, axis=1), expected)

    @dense_sparse
    def test_1d_weights_with_axis_0(self, array):
        x = array([[1, 1, np.nan, 1],
                   [np.nan, 1, 1, 1]])
        w = np.array([0.5, 1, 1, 1])

        np.testing.assert_equal(countnans(x, w, axis=0), [.5, 0, 1, 0])

    @dense_sparse
    def test_1d_weights_with_axis_1(self, array):
        x = array([[1, 1, np.nan, 1],
                   [np.nan, 1, 1, 1]])
        w = np.array([0.5, 1])

        np.testing.assert_equal(countnans(x, w, axis=1), [.5, 1])

    @dense_sparse
    def test_2d_weights(self, array):
        # pylint: disable=bad-whitespace
        x = array([[np.nan, np.nan, 1,      1 ],
                   [     0, np.nan, 2, np.nan ]])
        w = np.array([[1, 2, 3, 4],
                      [5, 6, 7, 8]])

        np.testing.assert_equal(countnans(x, w), 17)
        np.testing.assert_equal(countnans(x, w, axis=0), [1, 8, 0, 8])
        np.testing.assert_equal(countnans(x, w, axis=1), [3, 14])

    @dense_sparse
    def test_dtype(self, array):
        x = array([0, np.nan, 2, 3])
        w = np.array([0, 1.5, 0, 0])

        self.assertIsInstance(countnans(x, w, dtype=np.int32), np.int32)
        self.assertEqual(countnans(x, w, dtype=np.int32), 1)
        self.assertIsInstance(countnans(x, w, dtype=np.float64), np.float64)
        self.assertEqual(countnans(x, w, dtype=np.float64), 1.5)


class TestBincount(unittest.TestCase):
    @dense_sparse
    def test_count_nans(self, array):
        x = array([0, 0, 1, 2, np.nan, 2])
        expected = 1

        np.testing.assert_equal(bincount(x)[1], expected)

    @dense_sparse
    def test_adds_empty_bins(self, array):
        x = array([0, 1, 3, 5])
        expected = [1, 1, 0, 1, 0, 1]

        np.testing.assert_equal(bincount(x)[0], expected)

    @dense_sparse
    def test_maxval_adds_empty_bins(self, array):
        x = array([1, 1, 1, 2, 3, 2])
        max_val = 5
        expected = [0, 3, 2, 1, 0, 0]

        np.testing.assert_equal(bincount(x, max_val=max_val)[0], expected)

    @dense_sparse
    def test_maxval_doesnt_truncate_values_when_too_small(self, array):
        x = array([1, 1, 1, 2, 3, 2])
        max_val = 1
        expected = [0, 3, 2, 1]

        np.testing.assert_equal(bincount(x, max_val=max_val)[0], expected)

    @dense_sparse
    def test_minlength_adds_empty_bins(self, array):
        x = array([1, 1, 1, 2, 3, 2])
        minlength = 5
        expected = [0, 3, 2, 1, 0]

        np.testing.assert_equal(bincount(x, minlength=minlength)[0], expected)

    @dense_sparse
    def test_weights(self, array):
        x = array([0, 0, 1, 1, 2, 2, 3, 3])
        w = np.array([1, 2, 0, 0, 1, 1, 0, 1])

        expected = [3, 0, 2, 1]
        np.testing.assert_equal(bincount(x, w)[0], expected)

    @dense_sparse
    def test_weights_with_nans(self, array):
        x = array([0, 0, 1, 1, np.nan, 2, np.nan, 3])
        w = np.array([1, 2, 0, 0, 1, 1, 0, 1])

        expected = [3, 0, 1, 1]
        np.testing.assert_equal(bincount(x, w)[0], expected)

    @dense_sparse
    def test_weights_with_transposed_x(self, array):
        x = array([0, 0, 1, 1, 2, 2, 3, 3]).T
        w = np.array([1, 2, 0, 0, 1, 1, 0, 1])

        expected = [3, 0, 2, 1]
        np.testing.assert_equal(bincount(x, w)[0], expected)

    @dense_sparse
    def test_all_nans(self, array):
        x = array([np.nan] * 5)
        expected = []

        np.testing.assert_equal(bincount(x)[0], expected)

    @dense_sparse
    def test_all_zeros_or_nans(self, array):
        """Sparse arrays with only nans with no explicit zeros will have no non
        zero indices. Check that this counts the zeros properly."""
        x = array([np.nan] * 5 + [0] * 5)
        expected = [5]

        np.testing.assert_equal(bincount(x)[0], expected)


class TestUnique(unittest.TestCase):
    @dense_sparse
    def test_returns_unique_values(self, array):
        # pylint: disable=bad-whitespace
        x = array([[-1., 1., 0., 2., 3., np.nan],
                   [ 0., 0., 0., 3., 5., np.nan],
                   [-1., 0., 0., 1., 7.,     6.]])
        expected = [-1, 0, 1, 2, 3, 5, 6, 7, np.nan, np.nan]

        np.testing.assert_equal(unique(x, return_counts=False), expected)

    @dense_sparse
    def test_returns_counts(self, array):
        # pylint: disable=bad-whitespace
        x = array([[-1., 1., 0., 2., 3., np.nan],
                   [ 0., 0., 0., 3., 5., np.nan],
                   [-1., 0., 0., 1., 7.,     6.]])
        expected = [2, 6, 2, 1, 2, 1, 1, 1, 1, 1]

        np.testing.assert_equal(unique(x, return_counts=True)[1], expected)

    def test_sparse_explicit_zeros(self):
        # Use `lil_matrix` to fix sparse warning for matrix construction
        x = lil_matrix(np.eye(3))
        x[0, 1] = 0
        x[1, 0] = 0
        x = x.tocsr()
        # Test against identity matrix
        y = csr_matrix(np.eye(3))

        np.testing.assert_array_equal(
            unique(y, return_counts=True),
            unique(x, return_counts=True),
        )

    @dense_sparse
    def test_nanunique_ignores_nans_in_values(self, array):
        # pylint: disable=bad-whitespace
        x = array([[-1., 1., 0., 2., 3., np.nan],
                   [ 0., 0., 0., 3., 5., np.nan],
                   [-1., 0., 0., 1., 7.,     6.]])
        expected = [-1, 0, 1, 2, 3, 5, 6, 7]

        np.testing.assert_equal(nanunique(x, return_counts=False), expected)

    @dense_sparse
    def test_nanunique_ignores_nans_in_counts(self, array):
        # pylint: disable=bad-whitespace
        x = array([[-1., 1., 0., 2., 3., np.nan],
                   [ 0., 0., 0., 3., 5., np.nan],
                   [-1., 0., 0., 1., 7.,     6.]])
        expected = [2, 6, 2, 1, 2, 1, 1, 1]

        np.testing.assert_equal(nanunique(x, return_counts=True)[1], expected)


class TestArrayEqual(unittest.TestCase):
    @dense_sparse
    def test_same_matrices(self, array):
        x = array([0, 1, 0, 0, 2])
        self.assertTrue(array_equal(x, x))

    @dense_sparse
    def test_with_different_shapes(self, array):
        x = array(np.eye(4))
        y = array(np.eye(5))
        self.assertFalse(array_equal(x, y))

    @dense_sparse
    def test_with_different_values(self, array):
        x = array([0, 1, 0, 0, 2])
        y = array([0, 3, 0, 0, 2])
        self.assertFalse(array_equal(x, y))


class TestNanModeAppVeyor(unittest.TestCase):
    def test_appveyour_still_not_onscipy_1_2_0(self):
        import scipy
        from distutils.version import StrictVersion
        import os

        if os.getenv("APPVEYOR") and \
                StrictVersion(scipy.__version__) >= StrictVersion("1.2.0"):
            self.fail("Appveyor now uses Scipy 1.2.0; revert changes in "
                      "the last three commits (bde2cbe, 7163448, ab0f31d) "
                      "of gh-3480. Then, remove this test.")
