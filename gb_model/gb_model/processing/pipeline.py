import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

from gb_model.config import config as cfg
from gb_model.processing import preprocessing as ppg
from gb_model.processing import features as fts
from gb_model.processing import prediction as pdn


# Weather data preprocessing
wthr_pipe = Pipeline(
	[
		('time_converter', ppg.TimeConverter(timezones=cfg.TZ_OFFSETS)),
		('time_reindexer', ppg.TimeReindexer()),
		('missing_imputer', ppg.MissingImputer(cub_vars=cfg.CUB_VARS, lin_vars=cfg.LIN_VARS)),
		('data_copier', ppg.DataCopier())
	]
)


# Feature engineering
feat_pipe = Pipeline(
	[
		('weather_extractor', fts.WeatherExtractor()),
		('time_extractor', fts.TimeExtractor()),
		('holiday_extractor', fts.HolidayExtractor(countries=cfg.COUNTRIES)),
		('feat_selector', fts.FeatSelector(feats=cfg.FEATS))
	]
)


# Prediction
def pred_pipe(df, rare_path, mean_path, sclr_path, model_path,
               use_xgb=True,
               sqft_var='square_feet',
               target_var='meter_reading'):

	"""
	Make predictions using LightGBM or XGBoost.

	:param df: (Pandas dataframe) preprocessed data with listed variables
	:param rare_path: (string) path to trained rare label categorical encoders
	:param mean_path: (string) path to trained mean categorical encoders
	:param sclr_path: (string) path to trained standard scalers
	:param model_path: (String) path to trained LightGBM models
	:param use_xgb: (boolean) whether or not to predict using a XGBoost model
	:param sqft_var: (String) name of square footage variable
	:param target_var: (String) name of target variable

	:return: predictions in a list
	"""

	df = df.copy()
	df.reset_index(inplace=True)
	tmp = df[['index', 'site_id', 'meter']].copy()
	df.drop(['index', 'site_id'], axis=1, inplace=True)

	df_list = pdn.split(df)
	preds = []

	for i in range(4):
		re = joblib.load(rare_path + str(i) + '.pkl')
		me = joblib.load(mean_path + str(i) + '.pkl')
		ss = joblib.load(sclr_path + str(i) + '.pkl')
		X = pdn.transform(df_list[i], re, me, ss)

		y_pred = pdn.predict(X, model_path + str(i) + '.pkl', use_xgb=use_xgb)
		y = df_list[i][[sqft_var]].copy()
		y[target_var] = y_pred
		y = pdn.inverse_transform(y)
		preds.append(y)

	pred = pd.concat(preds).sort_index().reset_index()
	pred = pd.merge(tmp, pred, on='index', how='left')
	pred = pdn.convert_site0_units(pred)
	
	pred = pred[target_var].tolist()
	return pred