import os.path
import uuid

import numpy as np
import pandas as pd
from flask import session

import AppConfig
from FlaskCache import cache
from auth import AppIDAuthProvider


class ResidualService:

    @classmethod
    @cache.memoize(timeout=50000,
                   args_to_ignore=['df', 'session_store'])
    def calculate_residuals(cls, df,
                            df_name,
                            observed_smoothing_constant=100,
                            ambient_smoothing_constant=500,
                            points_to_clip=None,
                            session_store=None,
                            purpose='display'):

        extracted_path = None
        if session_store:
            extracted_path = os.path.join(AppConfig.PROJECT_ROOT, "data",
                                          session_store[AppIDAuthProvider.APPID_USER_NAME], "processed",
                                          f'{session_store[AppConfig.WORKING_DATASET]}_resid.csv')

        print('Calculate Residuals got called')

        df['id'] = [uuid.uuid4() for _ in range(len(df.index))]

        df.set_index('Datetime', inplace=True)
        df = df[~df.index.duplicated(keep='first')]
        df = df.sort_index().reset_index()

        df['Magnetic_Field_Smoothed'] = df['Magnetic_Field'].rolling(window=observed_smoothing_constant,
                                                                     win_type='boxcar', center=True,
                                                                     min_periods=1).mean()

        df['Magnetic_Field_Ambient'] = df['Magnetic_Field_Smoothed'] \
            .rolling(window=ambient_smoothing_constant,
                     win_type='boxcar',
                     center=False,
                     min_periods=1).mean()

        df['Baseline'] = df['Magnetic_Field_Smoothed'] - df['Magnetic_Field_Ambient']

        if purpose == 'save':
            df.to_csv(extracted_path)

        return df if purpose != 'save' else extracted_path

    @classmethod
    @cache.memoize(timeout=50000,
                   args_to_ignore=['df', 'session_store'])
    def calculate_residuals_with_clip(cls, df,
                                      df_name,
                                      observed_smoothing_constant=100,
                                      ambient_smoothing_constant=500,
                                      points_to_clip=None,
                                      session_store=None,
                                      min_val=None,
                                      max_val=None,
                                      purpose='save'):

        if min_val and max_val:
            df['Magnetic_Field'] = df['Magnetic_Field'].mask(df['Magnetic_Field'].le(float(min_val)))

            df['Magnetic_Field'] = df['Magnetic_Field'].mask(df['Magnetic_Field'].ge(float(max_val)))

            df['Magnetic_Field'] = df['Magnetic_Field'].interpolate(method='linear')

        if len(points_to_clip) > 0:
            df.loc[points_to_clip, 'Magnetic_Field'] = np.nan
            df['Magnetic_Field'] = df['Magnetic_Field'].interpolate(method='linear')

        return cls.calculate_residuals(df, df_name=None,
                                       ambient_smoothing_constant=ambient_smoothing_constant,
                                       observed_smoothing_constant=observed_smoothing_constant,
                                       points_to_clip=points_to_clip,
                                       purpose=purpose,
                                       session_store=session)

    @classmethod
    @cache.memoize(timeout=50000, args_to_ignore=['df'])
    def calculate_diurnal_correction(cls,
                                     df_surf: pd.DataFrame,
                                     df_obs: pd.DataFrame, session_store):

        obs_ids = ';'.join(session_store[AppConfig.OBS_DATA_SELECTED])

        extracted_path = os.path.join(AppConfig.PROJECT_ROOT, "data",
                                      session_store[AppIDAuthProvider.APPID_USER_NAME], "processed",
                                      f'{session_store[AppConfig.SURVEY_DATA_SELECTED]}_{obs_ids}_durn.csv')

        if os.path.exists(extracted_path):
            return pd.read_csv(extracted_path)

        print('Calculate Diurnal got called')

        min_survey_date = df_surf['Datetime'].min()
        max_survey_date = df_surf['Datetime'].max()

        df_obs = df_obs[(df_obs['Datetime'] >= min_survey_date) & (df_obs['Datetime'] <= max_survey_date)]

        df_surf['Datetime'] = pd.to_datetime(df_surf['Datetime'], format='mixed')
        df_obs['Datetime'] = pd.to_datetime(df_obs['Datetime'], format='mixed')

        df_surf.set_index('Datetime', inplace=True)
        df_obs.set_index('Datetime', inplace=True)

        survey_sampling_rate = df_surf.head(10000).index.to_series().diff().median().total_seconds()
        observatory_sampling_rate = df_obs.head(10000).index.to_series().diff().median().total_seconds()

        if observatory_sampling_rate != survey_sampling_rate:

            if 0 < survey_sampling_rate < 1:
                sample_rate = f'{str(survey_sampling_rate).split(".")[-1].ljust(3, "0")}ms'
            else:
                sample_rate = f'{survey_sampling_rate}s'

            df_obs = df_obs[~df_obs.index.duplicated(keep='first')]
            df_obs = df_obs.resample(sample_rate).interpolate(method='linear', limit=5, limit_direction='both')

        df_obs = df_obs[(df_obs.index >= df_surf.index.min()) & (df_obs.index <= df_surf.index.max())]

        df_obs = df_obs[df_obs.index.isin(df_surf.index)].sort_index()
        df_obs['Magnetic_Field_Smoothed'] = df_obs['Magnetic_Field'] \
            .rolling(window=100, min_periods=1, win_type='boxcar', center=True).mean()
        df_obs['Magnetic_Field_Smoothed'] = df_obs['Magnetic_Field_Smoothed'] - df_obs['Magnetic_Field_Smoothed'].mean()

        df_surf = df_surf[df_surf.index.isin(df_obs.index)].sort_index()

        df_surf['Magnetic_Field_Corrected'] = df_surf['Magnetic_Field'] - df_obs['Magnetic_Field_Smoothed'].abs()

        df_surf['Magnetic_Field_Corrected'] = df_surf['Magnetic_Field_Corrected'].fillna(df_surf['Magnetic_Field'])

        df_to_return = df_surf.dropna(subset=['Magnetic_Field_Corrected']).reset_index()
        df_to_return.to_csv(extracted_path)

        return df_to_return
