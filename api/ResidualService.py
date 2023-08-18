import uuid

from FlaskCache import cache


class ResidualService:

    @classmethod
    @cache.memoize(timeout=50000, args_to_ignore=['df'])
    def calculate_residuals(cls, df, df_name, observed_smoothing_constant=100, ambient_smoothing_constant=500):
        print('Calculate Residuals got called')
        # df = df[(df['Easting'] != '*') | (df['Northing'] != '*')].dropna()
        #
        # df['Easting'] = df['Easting'].astype(float)
        # df['Northing'] = df['Northing'].astype(float)
        # df['Magnetic_Field'] = df['Magnetic_Field'].astype(float)
        # df['Latitude'] = df['Latitude'].astype(float)
        # df['Longitude'] = df['Longitude'].astype(float)
        #
        # df['Magnetic_Field'] = df['Magnetic_Field'].astype(float)

        # df = df.dropna()
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
