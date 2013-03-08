# -*- coding: utf-8 -*-
"""Class to gather and analyse various metal line statistics"""

import numpy as np
import hdfsim
import halocat
import spectra
import matplotlib.pyplot as plt

class HaloSpectra(spectra.Spectra):
    """Generate metal line spectra from simulation snapshot"""
    def __init__(self,num, base, minpart = 400, nbins = 1024, cloudy_dir="/home/spb/codes/ArepoCoolingTables/tmp_spb/"):
        #Load halo centers to push lines through them
        f = hdfsim.get_file(num, base, 0)
        self.OmegaM = f["Header"].attrs["Omega0"]
        self.box = f["Header"].attrs["BoxSize"]
        self.npart=f["Header"].attrs["NumPart_Total"]+2**32*f["Header"].attrs["NumPart_Total_HighWord"]
        min_mass = self.min_halo_mass(minpart)
        f.close()
        (ind, self.sub_mass, cofm, self.sub_radii) = halocat.find_wanted_halos(num, base, min_mass)
        self.NumLos = np.size(self.sub_mass)*6
        #Random integers from [1,2,3]
#         axis = np.random.random_integers(3, size = self.NumLos)
        #All through y axis
        axis = np.ones(self.NumLos)
        axis[self.NumLos/3:2*self.NumLos/3] = 2
        axis[2*self.NumLos/3:self.NumLos] = 3
        cofm = np.repeat(cofm,6,axis=0)
        axis = np.repeat(axis,2)
        #Perturb the second set of sightlines within the virial radius
        np.random.seed(23)
        cofm[self.NumLos/2:] += (np.random.random_sample((self.NumLos/2,3))-0.5)*np.tile(np.repeat(self.sub_radii,3),(3,1)).T*2
        spectra.Spectra.__init__(self,num, base, cofm, axis, nbins, cloudy_dir)

    def min_halo_mass(self, minpart = 400):
        """Min resolved halo mass in internal Gadget units (1e10 M_sun)"""
        #This is rho_c in units of h^-1 1e10 M_sun (kpc/h)^-3
        rhom = 2.78e+11* self.OmegaM / 1e10 / (1e3**3)
        #Mass of an SPH particle, in units of 1e10 M_sun, x omega_m/ omega_b.
        target_mass = self.box**3 * rhom / self.npart[0]
        min_mass = target_mass * minpart
        return min_mass

    def absorption_distance(self):
        """Compute X(z), the absorption distance per sightline (eq. 9 of Nagamine et al 2003)
        in dimensionless units."""
        #h * 100 km/s/Mpc in h/s
        h100=3.2407789e-18
        #Units: h/s   s/m                        kpc/h      m/kpc
        return h100/self.light*(1+self.red)**2*self.box*self.KPC

    def absorption_distance_dz(self):
        """Compute dX/dz = H_0 (1+z)^2 / H(z) (which is independent of h)"""
        zp1 = 1+self.red
        return zp1**2/np.sqrt(self.OmegaM*zp1**3+(1-self.OmegaM))

    def vel_width_hist(self, tau, col_rho, dv=0.1):
        """
        To avoid having to compute a representative sample of sightlines
        (since we will only use the 0.1% of them that are DLAs) we compute
        the fraction of sightlines that are in this velocity bin out a
        representative sample of DLAs.

        This also matches the data from Prochaska.
        However, it does not match Pontzen 2008, who
        and multiply by the DLA fraction, obtained from the cddf.

        So we have f(N) = d n/ dv dX
        and n(N) = number of absorbers per sightline in this velocity bin.
        ie, f(N) = n / Δv / ΔX
        Note f(N) has dimensions of s/km, because v has units of km/s and X is dimensionless.

        Parameters:
            tau - optical depth along sightline
            dv - bin spacing

        Returns:
            (v, f_table) - v (binned in log) and corresponding f(N)
        """
        vel_width = self.vel_width(tau)
        nlos = np.shape(tau)[0]
        v_table = 10**np.arange(0, np.log10(np.max(vel_width)), dv)
        bin = np.array([(v_table[i]+v_table[i+1])/2. for i in range(0,np.size(v_table)-1)])
        dX=self.absorption_distance()
        ind = np.where(np.log10(col_rho) > 20.3)
        nn = np.histogram(vel_width[ind],v_table)[0] / (1.*np.size(vel_width[ind]))
        width = np.array([v_table[i+1]-v_table[i] for i in range(0,np.size(v_table)-1)])
        vels=nn/(width*dX)
        return (bin, vels)

    def plot_vel_width(self, tau, col_rho, dv=0.1):
        """Plot the velocity widths of this snapshot"""
        (bin, vels) = self.vel_width_hist(tau,col_rho, dv)
        plt.loglog(bin, vels)

    def plot_spectrum(self, tau, i):
        """Plot the spectrum of a line, centered on the deepest point,
           and marking the 90% velocity width."""
        #  Size of a single velocity bin
        tot_tau = np.sum(tau[i,:])
        #Deal with periodicity by making sure the deepest point is in the middle
        tau_l = tau[i,:]
        max = np.max(tau_l)
        ind_m = np.where(tau_l == max)[0][0]
        tau_l = np.roll(tau_l, np.size(tau_l)/2- ind_m)
        plt.plot(np.arange(0,np.size(tau_l))*self.dvbin,np.exp(-tau_l))
        cum_tau = np.cumsum(tau_l)
        ind_low = np.where(cum_tau > 0.05 * tot_tau)
        low = ind_low[0][0]*self.dvbin
        ind_high = np.where(cum_tau > 0.95 * tot_tau)
        high = ind_high[0][0]*self.dvbin
        if high - low > 0:
            plt.plot([low,low],[0,1])
            plt.plot([high,high],[0,1])
        plt.text(high+self.dvbin*30,0.5,r"$\delta v_{90} = "+str(np.round(high-low,1))+r"$")
        plt.ylim(-0.05,1.05)
        plt.xlim(0,np.size(tau_l)*self.dvbin)

