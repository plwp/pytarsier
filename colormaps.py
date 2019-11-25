import numpy as np

def greyscale():
    colors = np.zeros((256,3))
    for i in range(colors.shape[0]):
        colors[i][0] = i
        colors[i][1] = i
        colors[i][2] = i
        #colors[i][3] = i
    return colors.astype('uint8')

def redscale():
    colors = np.zeros((256,4))
    for i in range(colors.shape[0]):
        val = i / 16.
        val *= val
        val += 100.
        val = min(val, 255.)
        logval = 255 * (np.log(i+1) / np.log(256))
        logval = min(255., logval)
        logval = max(0., logval)
        colors[i][0] = logval
        colors[i][1] = 255
        colors[i][2] = val
        colors[i][3] = 0
    return colors.astype('uint8')

def reverse_greenscale():
    colors = np.zeros((256,4))
    for i in range(colors.shape[0]):
        val = i / 16.
        val *= val
        val = min(255., val)
        logval = 255 * (np.log(i+1) / np.log(256))
        logval = min(255., logval)
        logval = max(0., logval)

        colors[i][0] = (255 - val) 
        colors[i][1] = 128 - logval/2
        colors[i][2] = 255
        colors[i][3] = 0
    return colors.astype('uint8')
