function write_splits(csvPath, outPath)
%WRITE_SPLITS  Patient-level train/validation/test split. Never split on image id.
%   csvPath has columns patient and image (or id). Writes data/splits.json.

    arguments
        csvPath (1,1) string
        outPath (1,1) string = ""
    end

    repo = fileparts(fileparts(fileparts(mfilename("fullpath"))));
    if strlength(outPath) == 0
        outPath = fullfile(repo, "data", "splits.json");
    end
    if ~isfile(csvPath)
        error("nx:splits:missingCsv", "Label CSV %s is not present", csvPath);
    end

    T = readtable(csvPath);
    names = lower(string(T.Properties.VariableNames));
    if any(names == "patient")
        pid = string(T{:, names == "patient"});
    elseif any(names == "patient_id")
        pid = string(T{:, names == "patient_id"});
    else
        error("nx:splits:noPatient", "CSV must have a patient column");
    end
    if any(names == "image")
        img = string(T{:, names == "image"});
    elseif any(names == "id")
        img = string(T{:, names == "id"});
    else
        error("nx:splits:noImage", "CSV must have an image or id column");
    end

    patients = unique(pid, "stable");
    rng(26038);
    patients = patients(randperm(numel(patients)));
    n = numel(patients);
    nTrain = floor(0.70 * n);
    nVal = floor(0.15 * n);
    trainP = patients(1:nTrain);
    valP = patients(nTrain+1:nTrain+nVal);
    testP = patients(nTrain+nVal+1:end);

    S = struct();
    S.level = "patient";
    S.train = img(ismember(pid, trainP));
    S.validation = img(ismember(pid, valP));
    S.test = img(ismember(pid, testP));

    if ~isfolder(fileparts(outPath))
        mkdir(fileparts(outPath));
    end
    fid = fopen(outPath, "w");
    fwrite(fid, jsonencode(S, PrettyPrint=true));
    fclose(fid);
    fprintf("wrote %s\n", outPath);
end
