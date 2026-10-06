function [rgb, gray, green, fov] = nx_fov(imgPath)
%NX_FOV  Load a fundus image and estimate the illuminated field of view.
%   [rgb, gray, green, fov] = nx_fov(imgPath)
%   rgb is uint8 HxWx3, gray and green are double in [0, 1], fov is logical.

    arguments
        imgPath (1,1) string {mustBeFile}
    end

    rgb = imread(imgPath);
    if ndims(rgb) == 2 %#ok<ISMAT>
        rgb = repmat(rgb, 1, 1, 3);
    elseif size(rgb, 3) > 3
        rgb = rgb(:, :, 1:3);
    end

    I = im2double(rgb);
    gray = rgb2gray(I);
    green = I(:, :, 2);
    % Portable cameras vignette to a dark surround. A fixed intensity cut is enough
    % to measure FOV area; circularity of that mask catches a partial field.
    fov = gray > 0.04;
    fov = bwareaopen(fov, 500);
    fov = imfill(fov, "holes");
end
