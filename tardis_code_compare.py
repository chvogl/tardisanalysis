import os
import numpy as np
import pandas as pd
import astropy.units as units

from pyne import nucname


class CodeComparisonOutputFile(object):
    first_column_name = 'VEL'

    def __init__(self, times, data_table, model_name, data_first_column):
        self.times = times
        self.data_table = data_table
        if not data_first_column is None:
            self.data_table.insert(0, 'wav', data_first_column)
        self.model_name = model_name

    @property
    def times_str(self):
        return ' '.join([str(time) for time in self.times])

    @property
    def fname(self):
        return self.data_type + '_{}_tardis.txt'.format(self.model_name)

    def write(self, dest='.'):
        path = os.path.join(dest, self.fname)
        with open(path, mode='w+') as f:
            f.write('#NTIMES: {}\n'.format(len(self.times)))
            f.write('#N{}: {}\n'.format(self.first_column_name,
                                        len(self.data_table)))
            f.write('#TIMES[d]: ' + self.times_str + '\n')
            f.write(self.column_description + '\n')
            self.data_table.to_csv(f, index=False, float_format='%.6E',
                                   sep=' ', header=False)

    @staticmethod
    def get_times_from_simulations(simulations):
        times = [
            sim.model.time_explosion.to(units.day).value for sim in simulations
        ]
        return times

    @classmethod
    def from_simulations(cls, simulations, model_name):
        times = cls.get_times_from_simulations(simulations)
        data_table = cls.get_data_table(simulations)
        data_first_column = cls.get_data_first_column(simulations)
        return cls(times, data_table, model_name, data_first_column)

    @staticmethod
    def get_data_first_column(simulations):
        pass

    @staticmethod
    def get_data_table(simulations):
        pass


class SpectralOutputFile(CodeComparisonOutputFile):
    data_type = 'spectra'
    first_column_name = 'WAVE'
    column_description = ('#wavelength[Ang] flux_t0[erg/s/Ang] '
                          'flux_t1[erg/s/Ang] ... flux_tn[erg/s/Ang]')

    @staticmethod
    def get_data_first_column(simulations):
        return simulations[0].runner.spectrum.wavelength.value

    @staticmethod
    def get_data_table(simulations):
        spectra = [
            sim.runner.spectrum_integrated.luminosity_density_lambda.value
            for sim in simulations
        ]
        return pd.DataFrame(spectra).T


class VelocityInterpolatedOutputFile(CodeComparisonOutputFile):
    @classmethod
    def get_data_first_column(cls, simulations):
        return cls.get_velocity_grid_from_simulations(simulations)

    @classmethod
    def get_data_table(cls, simulations):
        v_interp = cls.get_data_first_column(simulations)

        interpolated_values = []
        for sim in simulations:
            v = sim.model.v_middle.to(units.km / units.s).value
            interpolation_values = cls.get_interpolation_values(sim)
            interpolated = np.interp(v_interp, v, interpolation_values,
                                     left=1e-99, right=1e-99)
            interpolated_values.append(interpolated)
        return pd.DataFrame(np.vstack(interpolated_values)).T

    @staticmethod
    def get_velocity_grid_from_simulations(simulations):
        v_middles = [
            sim.model.v_middle.to(units.km / units.s).value for sim in simulations
        ]
        min_delta_v = np.min([np.diff(v_middle).min() for v_middle in v_middles])
        v_min = np.min([v_middle.min() for v_middle in v_middles])
        v_max = np.max([v_middle.max() for v_middle in v_middles])
        N_shells = round((v_max - v_min) / min_delta_v) + 2
        return np.linspace(v_min, v_max, N_shells)

    @staticmethod
    def get_interpolation_values(sim):
        pass


class TGasOutputFile(VelocityInterpolatedOutputFile):
    data_type = 'tgas'
    column_description = '#vel_mid[km/s] Tgas_t0[K] Tgas_t1[K] ... Tgas_tn[K]'

    @staticmethod
    def get_interpolation_values(sim):
        return sim.plasma.t_electrons


class EdenOutputFile(VelocityInterpolatedOutputFile):
    data_type = 'eden'
    column_description = '#vel_mid[km/s] ne_t0[/cm^3] ne_t1[/cm^3] … ne_tn[/cm^3]'

    @staticmethod
    def get_interpolation_values(sim):
        return sim.plasma.electron_densities.values



class IonFracOutputFile(VelocityInterpolatedOutputFile):
    data_type = 'ionfrac'
    column_description = '#vel_mid[km/s]'

    def __init__(self, times, data_table, model_name, data_first_column,
                 vel_mid, species='Ca'):
        super().__init__(times, data_table, model_name, data_first_column)
        self.species = species
        self.vel_mid = vel_mid
        self.species_num = nucname.name_zz[species]
        ion_columns = ' '.join([''.join([species,str(i)]) for i in range(self.species_num)])
        self.column_description = ' '.join([self.column_description, ion_columns])

    
    @property
    def fname(self):
        return self.data_type + '_{}_{}_tardis.txt'.format(self.species,
                                                           self.model_name)
    
    def write(self, dest='.'):
        path = os.path.join(dest, self.fname)
        with open(path, mode='w+') as f:
            f.write('#NTIMES: {}\n'.format(len(self.times)))
            f.write('#NSTAGES: {}\n'.format(self.species_num))
            f.write('#TIMES[d]: ' + self.times_str + '\n#\n')
            for i, time in enumerate(self.times):
                f.write('#TIME: {}\n'.format(time))
                f.write('#NVEL: {}\n'.format(len(self.vel_mid)))
                ion_df = self.data_table[i].loc[self.species_num].T
                ion_df.insert(0, 'vel_mid', self.vel_mid)
                f.write(self.column_description + '\n')
                ion_df.to_csv(f, index=False, float_format='%.6E',
                                          sep=' ', header=False)

class PhysicalPropertyOutputFile(VelocityInterpolatedOutputFile):
    data_type = 'phys'
    column_description = '#vel_mid[km/s] temp[K] rho[gcc] ne[/cm^3] natom[/cm^3]'

    def __init__(self, times, data_table, model_name, data_first_column,
                 vel_mid, temp, rho, ne):
        super().__init__(times, data_table, model_name, data_first_column)
        self.vel_mid = vel_mid
        self.temp = temp
        self.rho = rho
        self.ne = ne

    @property
    def fname(self):
        return self.data_type + '_{}_tardis.txt'.format(self.model_name)

    def write(self, dest='.'):
        path = os.path.join(dest, self.fname)
        with open(path, mode='w+') as f:
            f.write('#NTIMES: {}\n'.format(len(self.times)))
            f.write('#TIMES[d]: ' + self.times_str + '\n#\n')
            for i, time in enumerate(self.times):
                f.write('#TIME: {}\n'.format(time))
                f.write('#NVEL: {}\n'.format(len(self.vel_mid)))
                natom = np.sum(self.data_table[i].values, axis=0)
                df = pd.DataFrame()
                df.insert(0, 'natom', natom)
                df.insert(0, 'ne', self.ne[i])
                df.insert(0, 'rho', self.rho[i])
                df.insert(0, 'temp', self.temp[i])
                df.insert(0, 'vel_mid', self.vel_mid)
                f.write(self.column_description + '\n')
                df.to_csv(f, index=False, float_format='%.6E',
                          sep=' ', header=False)