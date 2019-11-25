#!/usr/bin/python3

import sys
import os
import subprocess
import numpy as np
import nibabel as nib
import colormaps
import time

FIXED_OUT_N4 = 'n4out-fixed.nii.gz'
FLOATING_OUT_N4 = 'n4out-floating.nii.gz'
FIXED_OUT_BET = 'betout-fixed.nii.gz'
FLOATING_OUT_BET = 'betout-floating.nii.gz'
REG_OUT = 'warped.nii.gz'
REG_MAT = 'out0GenericAffine.mat'

def vistarsier_compare(c, p, min_val=-1., max_val=5., min_change=0.8, max_change=3.):
    """ VisTarsier's compare operation
    Parameters
    ----------
    c : ndarray
        The current volume
    p : ndarray
        The prior volume
    min_val : float
        The minimum value (measured in standard deviations) to consider
    max_val : float
        The maximum value (measured in standard deviations) to consider
    min_change : float
        The minimum change of value (measured in standard deviations) to consider
    max_change : float
        The maximum change of value (measured in standard deviations) to consider
    Returns
    -------
    change : ndarray
        The relevant change in signal.
    """
    print('Starting VisTarsier comparison...')
    # Get standard deviations for current and prior
    pstd = p.std()
    cstd = c.std()
    # Align prior standard deviation to current
    p = ((p - p.mean()) / pstd) * cstd + c.mean();

    # Here we could plot a histogram (which should show rough alignment)
    #minrange = np.min((p.min(), c.min()))
    #maxrange = np.max((p.max(), c.max()))
    #phist = np.histogram(p, 256, (minrange,maxrange))
    #chist = np.histogram(c, 256, (minrange,maxrange))

    #Calculate change
    change = c - p
    # Ignore change outside of minimuim and maximum values
    change[c < min_val*cstd] = 0
    change[p < min_val*pstd] = 0
    change[c > max_val*cstd] = 0
    change[p > max_val*pstd] = 0
    change[np.abs(change) < min_change*cstd] = 0
    change[np.abs(change) > max_change*cstd] = 0
    print('...VisTarsier comparison complete.')
    return change

def pre_process(floating, fixed):
    """Pre processes the nifti images using:
    ANTs N4BiasFieldCorrection -> FSL bet -> ANTs antsRegistration
    Parameters
    ----------
    floating : string
        Path to the floating nifti image
    fixed : string
        Path to the fixed nifti image

    Returns
    -------
    (floating, fixed) : tuple
        floating : string
            Path to the pre-processed floating image
        fixed : string
            Path to the pre-processed floating image
    """
    print('Preprocesing...')
    # ANTS N4 Bias correction
    print('N4BiasFieldCorrection for fixed volume started...')
    p1 = subprocess.Popen(['N4BiasFieldCorrection', '-i', fixed, '-o', FIXED_OUT_N4])
    print('N4BiasFieldCorrection for floating volume started...')
    p2 = subprocess.Popen(['N4BiasFieldCorrection', '-i', floating, '-o', FLOATING_OUT_N4])
    p1.wait()
    print('...N4BiasFieldCorrection for fixed volume complete.')
    p2.wait()
    print('...N4BiasFieldCorrection for floating volume complete.')

    print('FSL BET2 for fixed volume started...')
    p2 = subprocess.Popen(['fsl5.0-bet', FIXED_OUT_N4, FIXED_OUT_BET, '-f','0.4','-R'])
    print('FSL BET2 for floating volume started...')
    p1 = subprocess.Popen(['fsl5.0-bet', FLOATING_OUT_N4, FLOATING_OUT_BET, '-f','0.4','-R'])
    p1.wait()
    print('...FSL BET2 for fixed volume complete.')
    p2.wait()
    print('...FSL BET2 for floating volume complete.')

    os.remove(FLOATING_OUT_N4)
    os.remove(FIXED_OUT_N4)

    print('Starting antsRegistration...')
    subprocess.run([
        'antsRegistration',
        '--dimensionality','3', # Run ANTS on 3 dimensional image
        '--float', '1',
        '--interpolation', 'Linear',
        '--use-histogram-matching', '0',
        '--initial-moving-transform', f'[{FIXED_OUT_BET},{FLOATING_OUT_BET},1]',
        '--transform', 'Affine[0.1]',
        '--metric', f'MI[{FIXED_OUT_BET},{FLOATING_OUT_BET},1,32,Regular,0.25]', # Use mutal information (we're not normalizing intensity)
        '--convergence', '[1000x500x250x100,1e-6,10]',
        '--shrink-factors', '8x4x2x1',
        '--smoothing-sigmas', '3x2x1x0vox',
        '--output', f'[out,{REG_OUT}]'
    ])
    print('...antsRegistration complete.')

    os.remove(FLOATING_OUT_BET)
    os.remove(REG_MAT)

    return (REG_OUT,FIXED_OUT_BET)

def display_change(current, change):
    current = current.copy()
    current -= np.min(current)
    current /= np.max(current)
    current *= 255
    current = colormaps.greyscale()[current.astype('int')]

    # Get increase and decrease
    inc_change = change.clip(0, float('inf'))
    dec_change = change.clip(float('-inf'), 1)

    # Convert to color values
    inc_change -= np.min(inc_change)
    if np.max(inc_change) != 0:
        inc_change /= np.max(inc_change)
    inc_change *= 255
    inc_change = colormaps.redscale()[inc_change.astype('int')]

    # Convert to color values
    dec_change -= np.min(dec_change)
    if np.max(dec_change) != 0:
        dec_change /= np.max(dec_change)
    dec_change *= 255
    dec_change = colormaps.reverse_greenscale()[dec_change.astype('int')]

    # Apply increased signal colour
    inc_out = current.copy().astype('float64')
    inc_change = inc_change.astype('float64')
    inc_out[:,:,:,0] = inc_change[:,:,:,0]*inc_change[:,:,:,1]/255 + (255-inc_change[:,:,:,0])*current[:,:,:,0]/255
    inc_out[:,:,:,1] = inc_change[:,:,:,0]*inc_change[:,:,:,2]/255 + (255-inc_change[:,:,:,0])*current[:,:,:,1]/255
    inc_out[:,:,:,2] = inc_change[:,:,:,0]*inc_change[:,:,:,3]/255 + (255-inc_change[:,:,:,0])*current[:,:,:,2]/255

    # Apply decreased signal colour
    dec_out = current.copy().astype('float64')
    dec_change = dec_change.astype('float64')
    dec_out[:,:,:,0] = dec_change[:,:,:,0]*dec_change[:,:,:,1]/255 + (255-dec_change[:,:,:,0])*current[:,:,:,0]/255
    dec_out[:,:,:,1] = dec_change[:,:,:,0]*dec_change[:,:,:,2]/255 + (255-dec_change[:,:,:,0])*current[:,:,:,1]/255
    dec_out[:,:,:,2] = dec_change[:,:,:,0]*dec_change[:,:,:,3]/255 + (255-dec_change[:,:,:,0])*current[:,:,:,2]/255


    return (inc_out.astype('uint8'), dec_out.astype('uint8'))

def cleanup():
    if os.path.exists(FIXED_OUT_N4): os.remove(FIXED_OUT_N4)
    if os.path.exists(FLOATING_OUT_N4): os.remove(FLOATING_OUT_N4)
    if os.path.exists(FIXED_OUT_BET): os.remove(FIXED_OUT_BET)
    if os.path.exists(FLOATING_OUT_BET): os.remove(FLOATING_OUT_BET)
    if os.path.exists(REG_OUT): os.remove(REG_OUT)
    if os.path.exists(REG_MAT): os.remove(REG_MAT)

def save_in_color(data, q_form, path):
    # Create a datatype that nibabel can understand and save...
    rgb_dtype = np.dtype([('R', 'u1'), ('G', 'u1'), ('B', 'u1')])
    # Apply the datatype
    data = data.copy().view(dtype=rgb_dtype).reshape(data.shape[0:3])
    img = nib.Nifti1Image(data, q_form)
    nib.save(img, path)

if __name__ == '__main__':

    start = time.process_time()
    #parse args
    if len(sys.argv) < 3:
        print("Vistarsier requires at least a current and prior study.")
        print("Usage: vistarsier.py [prior.nii] [current.nii] [output-prefix](optional)")
        exit(100)

    try:
        # Initialise variables
        prior_path = sys.argv[1]
        current_path = sys.argv[2]
        output_prefix = ""
        if len(sys.argv) > 3:
            output_prefix  = sys.argv[3]
        print('Using:')
        print('     Prior : ', prior_path)
        print('   Current : ', current_path)
        print('Out prefix : ', output_prefix)
        print('*****************************************************************')
        print('')

        # Run biascorrection | skull stripping | registration
        prior_proc, current_proc = pre_process(prior_path, current_path)
        # Load pre-processed images
        pimg = nib.load(prior_proc)
        cimg = nib.load(current_proc)
        # Calculate change
        change = vistarsier_compare(cimg.get_fdata(), pimg.get_fdata())
        # Apply colourmaps
        print('Applying colormaps...')
        inc_output, dec_output = display_change(cimg.get_fdata(), change)
        # Save everything
        save_in_color(inc_output, cimg.header.get_qform(), f"{output_prefix}vt-increase.nii.gz")
        save_in_color(dec_output, cimg.header.get_qform(), f"{output_prefix}vt-decrease.nii.gz")
        print('...ALL DONE!')
        print(time.process_time() - start)
    finally:
        # Get rid of temp files
        cleanup()
