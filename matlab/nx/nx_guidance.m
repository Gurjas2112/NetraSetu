function key = nx_guidance(failureMode)
%NX_GUIDANCE  Map a quality failure mode to a localised retake instruction key.
%   Never returns the word "ungradeable". Keys match web/public/locales.

    arguments
        failureMode (1,1) string
    end

    switch failureMode
        case "defocus"
            key = "retake.defocus.hold_steady";
        case "underexposed"
            key = "retake.underexposed.nasal";
        case "overexposed"
            key = "retake.overexposed.reduce_light";
        case "partial_fov"
            key = "retake.partial_fov.centre";
        case "media_opacity"
            key = "retake.media_opacity.dilate";
        otherwise
            key = "retake.partial_fov.centre";
    end
end
