import logging
import shutil
import unittest

import numpy as np
import pandas as pd

from ..timeseries import TimeSeries
from ..utils import timeseries_generation as tg
from ..metrics import mape
from ..models import NaiveSeasonal, ExponentialSmoothing, ARIMA, Theta, FourTheta, FFT
from .. import SeasonalityMode, TrendMode, ModelMode
from ..logging import get_logger

logger = get_logger(__name__)

# (forecasting models, maximum error) tuples
models = [
    (ExponentialSmoothing(), 4.8),
    (ARIMA(0, 1, 1), 17.1),
    (ARIMA(1, 1, 1), 14.2),
    (Theta(), 11.3),
    (Theta(1), 20.2),
    (Theta(-1), 9.8),
    (FourTheta(1), 20.2),
    (FourTheta(-1), 9.8),
    (FourTheta(trend_mode=TrendMode.EXPONENTIAL), 5.5),
    (FourTheta(model_mode=ModelMode.MULTIPLICATIVE), 11.4),
    (FourTheta(season_mode=SeasonalityMode.ADDITIVE), 14.2),
    (FFT(trend='poly'), 11.4),
    (NaiveSeasonal(), 32.4),
]

try:
    from ..models import Prophet
    models.append((Prophet(), 13.5))
except ImportError:
    logger.warning('Prophet not installed - will be skipping Prophet tests')

try:
    from ..models import AutoARIMA
    models.append((AutoARIMA(), 13.7))
except ImportError:
    logger.warning('pmdarima not installed - will be skipping AutoARIMA tests')

try:
    from ..models import TCNModel
    TORCH_AVAILABLE = True
except ImportError:
    logger.warning('Torch not installed - will be skipping Torch models tests')
    TORCH_AVAILABLE = False


class ForecastingModelsTestCase(unittest.TestCase):

    # forecasting horizon used in runnability tests
    forecasting_horizon = 5

    # dummy timeseries for runnability tests
    np.random.seed(1)
    ts_gaussian = tg.gaussian_timeseries(length=100, mean=50)

    # real timeseries for functionality tests
    df = pd.read_csv('examples/AirPassengers.csv', delimiter=",")
    ts_passengers = TimeSeries.from_dataframe(df, 'Month', ['#Passengers'])
    ts_pass_train, ts_pass_val = ts_passengers.split_after(pd.Timestamp('19570101'))

    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    @unittest.skipUnless(TORCH_AVAILABLE, "requires torch")
    def tearDownClass(cls):
        shutil.rmtree('.darts')

    def test_models_runnability(self):
        for model, _ in models:
            model.fit(self.ts_gaussian)
            prediction = model.predict(self.forecasting_horizon)
            self.assertTrue(len(prediction) == self.forecasting_horizon)

    def test_models_performance(self):
        # for every model, check whether its errors do not exceed the given bounds
        for model, max_mape in models:
            model.fit(self.ts_pass_train)
            prediction = model.predict(len(self.ts_pass_val))
            current_mape = mape(prediction, self.ts_pass_val)
            self.assertTrue(current_mape < max_mape, "{} model exceeded the maximum MAPE of {}."
                            "with a MAPE of {}".format(str(model), max_mape, current_mape))

    def test_multivariate_input(self):
        es_model = ExponentialSmoothing()
        ts_passengers_enhanced = self.ts_passengers.add_datetime_attribute('month')
        with self.assertRaises(AssertionError):
            es_model.fit(ts_passengers_enhanced)
        es_model.fit(ts_passengers_enhanced["#Passengers"])
        with self.assertRaises(KeyError):
            es_model.fit(ts_passengers_enhanced["2"])

        if TORCH_AVAILABLE:
            tcn_model = TCNModel(n_epochs=1, input_size=2)
            with self.assertRaises(ValueError):
                tcn_model.fit(ts_passengers_enhanced)
            tcn_model.fit(ts_passengers_enhanced, ts_passengers_enhanced["Month"])
            with self.assertRaises(KeyError):
                tcn_model.fit(ts_passengers_enhanced, ts_passengers_enhanced["2"])
            tcn_model = TCNModel(n_epochs=1, input_size=2, output_size=2)
            with self.assertRaises(KeyError):
                tcn_model.fit(ts_passengers_enhanced, ts_passengers_enhanced[["#Passengers", "2"]])
            tcn_model.fit(ts_passengers_enhanced, ts_passengers_enhanced[["#Passengers", "Month"]])
