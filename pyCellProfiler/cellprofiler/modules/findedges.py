'''<b>FindEdges:</b> Identifies edges in an image, which can be used as the basis for object
identification or other downstream image processing.
<hr>
This module enhances the edges of objects in a grayscale image. All methods
other than Canny produce a grayscale image that can be thresholded using
the ApplyThreshold module to produce a mask of edges. The Canny algorithm
produces a binary image consisting of the edge pixels.

'''
#CellProfiler is distributed under the GNU General Public License.
#See the accompanying file LICENSE for details.
#
#Developed by the Broad Institute
#Copyright 2003-2009
#
#Please see the AUTHORS file for credits.
#
#Website: http://www.cellprofiler.org

__version__ = "$Revision$"

import numpy as np
from scipy.ndimage import convolve

import cellprofiler.cpmodule as cpm
import cellprofiler.settings as cps
import cellprofiler.cpimage as cpi
from cellprofiler.cpmath.filter import laplacian_of_gaussian
from cellprofiler.cpmath.filter import roberts, canny, sobel, hsobel, vsobel
from cellprofiler.cpmath.filter import prewitt, hprewitt, vprewitt, stretch
from cellprofiler.cpmath.otsu import otsu3

M_SOBEL = "Sobel"
M_PREWITT = "Prewitt"
M_ROBERTS = "Roberts"
M_LOG = "LoG"
M_CANNY = "Canny"

O_BINARY = "Binary"
O_GRAYSCALE = "Grayscale"

E_ALL = "All"
E_HORIZONTAL = "Horizontal"
E_VERTICAL = "Vertical"

class FindEdges(cpm.CPModule):

    module_name = "FindEdges"
    category = "Image Processing"
    variable_revision_number = 2

    def create_settings(self):
        self.image_name = cps.ImageNameSubscriber("Select the input image","None", 
                                                  doc = '''What did you call the image in which you want to find the edges?''')
        self.output_image_name = cps.ImageNameProvider("Name the output image","EdgedImage",
                                                    doc = '''What do you want to call the image with edges identified?''')
        self.wants_automatic_threshold = cps.Binary("Do you want to automatically calculate the threshold?", True,
                                                    doc = '''Automatic thresholding is done using a three-
                                                    category Otsu algorithm performed on the Sobel transform of the image.''')
        self.manual_threshold = cps.Float("Enter an absolute threshold between 0 and 1:",.2,0,1, doc = '''Alternatively,
                                                    you can pick a threshold.''')
        self.threshold_adjustment_factor = cps.Float("Enter the threshold adjustment factor (1 = no adjustment)",1)
        self.method = cps.Choice("Choose an edge-finding method:",
                                 [M_SOBEL, M_PREWITT, M_ROBERTS,
                                  M_LOG, M_CANNY], doc = '''There are several methods that can be used to identify edges:
                                  <ul><li>Sobel Method: finds edges using the Sobel approximation to the derivative. 
                                  The Sobel method derives a horizontal and vertical gradient measure and returns the 
                                  square-root of the sum of the two squared signals.</li>
                                  <li>Prewitt Method: finds edges using the Prewitt approximation to the derivative.
                                  It returns edges at those points where the gradient of the image is maximum.</li>
                                  <li>Roberts Method: finds edges using the Roberts approximation to the derivative. 
                                  The Roberts method looks for gradients in the diagonal and anti-diagonal directions 
                                  and returns the square-root of the sum of the two squared signals. The method is fast,
                                   but it creates diagonal artifacts that may need to be removed by smoothing.</li> 
                                  <li>LoG Method: This method applies a Laplacian of Gaussian filter to the image 
                                  and finds zero crossings. </li>
                                  <li>Canny Method - The Canny method finds edges by looking for local maxima 
                                  of the gradient of the image. The gradient is calculated using the derivative
                                   of a Gaussian filter. The method uses two thresholds, to detect strong and weak 
                                   edges, and includes the weak edges in the output only if they are connected to 
                                   strong edges. This method is therefore less likely than the others to be fooled 
                                   by noise, and more likely to detect true weak edges.</li></ul>''')
        self.direction = cps.Choice("Which edges do you want to find?",
                                    [ E_ALL, E_HORIZONTAL, E_VERTICAL], doc = '''This is the direction of the edges
                                    are you are identifying in the image (predominantly horizontal, predominantly vertical,
                                    or both).''')
        self.wants_automatic_sigma = cps.Binary("Do you want the Gaussian's sigma calculated automatically?", True)
        self.sigma = cps.Float("Enter the value for the Gaussian's sigma:", 10)
        self.wants_automatic_low_threshold = cps.Binary("Do you want the value for the low threshold to be calculated automatically?", True)
        self.low_threshold = cps.Float("Enter the value for the low threshold",.1,0,1)

    def settings(self):
        return [self.image_name, self.output_image_name, 
                self.wants_automatic_threshold, self.manual_threshold,
                self.threshold_adjustment_factor, self.method, 
                self.direction, self.wants_automatic_sigma, self.sigma,
                self.wants_automatic_low_threshold, self.low_threshold]

    def visible_settings(self):
        settings = [self.image_name, self.output_image_name]
        if self.method == M_CANNY:
            settings += [self.wants_automatic_threshold]
            if not self.wants_automatic_threshold.value:
                settings += [self.manual_threshold]
            settings += [self.threshold_adjustment_factor]
        settings += [self.method]
        if self.method in (M_SOBEL, M_PREWITT):
            settings += [self.direction]
        if self.method in (M_LOG, M_CANNY):
            settings += [self.wants_automatic_sigma]
            if not self.wants_automatic_sigma.value:
                settings += [self.sigma]
        if self.method == M_CANNY:
            settings += [self.wants_automatic_low_threshold]
            if not self.wants_automatic_low_threshold.value:
                settings += [self.low_threshold]
        return settings
    
    def run(self, workspace):
        image = workspace.image_set.get_image(self.image_name.value,
                                              must_be_grayscale = True)
        orig_pixels = image.pixel_data
        if image.has_mask:
            mask = image.mask
        else:
            mask = np.ones(orig_pixels.shape,bool)
        if self.method == M_SOBEL:
            if self.direction == E_ALL:
                output_pixels = sobel(orig_pixels, mask)
            elif self.direction == E_HORIZONTAL:
                output_pixels = hsobel(orig_pixels, mask)
            elif self.direction == E_VERTICAL:
                output_pixels = vsobel(orig_pixels, mask)
            else:
                raise NotImplementedError("Unimplemented direction for Sobel: %s",self.direction.value)
        elif self.method == M_LOG:
            sigma = self.get_sigma()
            size = int(sigma * 4)+1
            output_pixels = laplacian_of_gaussian(orig_pixels, mask, size, sigma)
        elif self.method == M_PREWITT:
            if self.direction == E_ALL:
                output_pixels = prewitt(orig_pixels)
            elif self.direction == E_HORIZONTAL:
                output_pixels = hprewitt(orig_pixels, mask)
            elif self.direction == E_VERTICAL:
                output_pixels = vprewitt(orig_pixels, mask)
            else:
                raise NotImplementedError("Unimplemented direction for Prewitt: %s",self.direction.value)
        elif self.method == M_CANNY:
            high_threshold = self.manual_threshold.value
            low_threshold = self.low_threshold.value
            if (self.wants_automatic_low_threshold.value or
                self.wants_automatic_threshold.value):
                sobel_image = sobel(orig_pixels, mask)
                low, high = otsu3(sobel_image[mask])
                if self.wants_automatic_low_threshold.value:
                    low_threshold = low * self.threshold_adjustment_factor.value
                if self.wants_automatic_threshold.value:
                    high_threshold = high * self.threshold_adjustment_factor.value
            output_pixels = canny(orig_pixels,mask, self.get_sigma(),
                                  low_threshold,
                                  high_threshold)
        elif self.method == M_ROBERTS:
            output_pixels = roberts(orig_pixels, mask)
        else:
            raise NotImplementedError("Unimplemented edge detection method: %s"%
                                      self.method.value)
        if not workspace.frame is None:
            figure = workspace.create_or_find_figure(subplots=(2,2))
            figure.subplot_imshow_grayscale(0,0, orig_pixels,
                                            "Original: %s"%
                                            self.image_name.value)
            if self.method == M_CANNY:
                # Canny is binary
                figure.subplot_imshow_bw(0,1, output_pixels,
                                         self.output_image_name.value)
            else:
                figure.subplot_imshow_grayscale(0,1,output_pixels,
                                                self.output_image_name.value)
            color_image = np.zeros((output_pixels.shape[0],
                                    output_pixels.shape[1],3))
            color_image[:,:,0] = stretch(orig_pixels)
            color_image[:,:,1] = stretch(output_pixels)
            figure.subplot_imshow_color(1,0, color_image,"Composite image")
        output_image = cpi.Image(output_pixels, parent_image = image)
        workspace.image_set.add(self.output_image_name.value, output_image)   
    
    def get_sigma(self):
        if self.wants_automatic_sigma.value:
            #
            # Constants here taken from FindEdges.m
            #
            if self.method == M_CANNY:
                return 1.0
            elif self.method == M_LOG:
                return 2.0
            else:
                raise NotImplementedError("Automatic sigma not supported for method %s."%self.method.value)
        else:
            return self.sigma.value
    
    def backwards_compatibilize(self, setting_values, variable_revision_number,
                                module_name, from_matlab):
        if from_matlab and variable_revision_number == 3:
            setting_values = [
                              setting_values[0], # ImageName
                              setting_values[1], # OutputName
                              setting_values[2] == cps.DO_NOT_USE, # Threshold
                              setting_values[2] 
                              if setting_values[2] != cps.DO_NOT_USE
                              else .5,
                              setting_values[3], # Threshold adjustment factor
                              setting_values[4], # Method
                              setting_values[5], # Filter size
                              setting_values[8], # Direction 
                              setting_values[9] == cps.DO_NOT_USE, # Sigma
                              setting_values[9] 
                              if setting_values[9] != cps.DO_NOT_USE
                              else 5,
                              setting_values[10] == cps.DO_NOT_USE, # Low threshold
                              setting_values[10] 
                              if setting_values[10] != cps.DO_NOT_USE
                              else .5]
            from_matlab = False
            variable_revision_number = 1
        
        if from_matlab == False and variable_revision_number == 1:
            # Ratio removed / filter size removed
            setting_values = setting_values[:6]+setting_values[7:]
            variable_revision_number = 2
        return setting_values, variable_revision_number, from_matlab
    
