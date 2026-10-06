function hex = nx_phash(gray)
%NX_PHASH  64-bit average hash of a grayscale image, as 16 lowercase hex characters.
%   This is a perceptual hash for near-duplicate flagging, not a cryptographic one.

    arguments
        gray (:,:) double
    end

    small = imresize(gray, [8 8], "bilinear");
    bits = small >= mean(small(:));
    packed = uint64(0);
    for k = 1:64
        packed = packed * uint64(2);
        if bits(k)
            packed = packed + uint64(1);
        end
    end
    hex = lower(dec2hex(packed, 16));
end
