import uuid

from FlaskCache import cache


class ResidualService:

    @classmethod
    @cache.memoize(timeout=50000, args_to_ignore=['df'])
    def calculate_residuals(cls, df, df_name, observed_smoothing_constant=100, ambient_smoothing_constant=500):
        print('Calculate Residuals got called')

        df['id'] = [uuid.uuid4() for _ in range(len(df.index))]

        df['Magnetic_Field_Smoothed'] = df['Magnetic_Field'].rolling(window=observed_smoothing_constant,
                                                                     win_type='boxcar', center=True,
                                                                     min_periods=1).mean()

        df['Magnetic_Field_Ambient'] = df['Magnetic_Field_Smoothed'] \
            .rolling(window=ambient_smoothing_constant,
                     win_type='boxcar',
                     center=True,
                     min_periods=1).mean()

        df['Baseline'] = df['Magnetic_Field_Smoothed'] - df['Magnetic_Field_Ambient']

        return df

    @classmethod
    @cache.memoize(timeout=50000, args_to_ignore=['df'])
    def calculate_durn_correction(cls, df_surf, df_obs):
        print('Calculate Residuals got called')

        df_surf['id'] = [uuid.uuid4() for _ in range(len(df_surf.index))]

        df['Magnetic_Field_Smoothed'] = df['Magnetic_Field'].rolling(window=observed_smoothing_constant,
                                                                     win_type='boxcar', center=True,
                                                                     min_periods=1).mean()

        df['Magnetic_Field_Ambient'] = df['Magnetic_Field_Smoothed'] \
            .rolling(window=ambient_smoothing_constant,
                     win_type='boxcar',
                     center=True,
                     min_periods=1).mean()

        df['Baseline'] = df['Magnetic_Field_Smoothed'] - df['Magnetic_Field_Ambient']

        return df
