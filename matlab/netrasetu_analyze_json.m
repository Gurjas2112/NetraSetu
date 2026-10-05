function txt = netrasetu_analyze_json(imgPath, outDir)
%NETRASETU_ANALYZE_JSON  Engine boundary: run netrasetu_analyze and return JSON text.
%   txt = netrasetu_analyze_json(imgPath, outDir) is the only function the Python gateway calls.
%   It returns a char row vector so no MATLAB struct crosses the engine boundary.

    arguments
        imgPath (1,1) string
        outDir (1,1) string
    end

    if exist("nx_config", "file") ~= 2
        addpath(fullfile(fileparts(mfilename("fullpath")), "nx"));
    end

    out = netrasetu_analyze(imgPath, outDir);
    txt = char(jsonencode(out));
end
