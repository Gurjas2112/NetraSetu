classdef tBuildDistrictTwin < matlab.unittest.TestCase
    %TBUILDDISTRICTTWIN  Smoke-test programmatic SimEvents assembly (HUMAN-VERIFY sim()).

    properties
        RepoRoot string
        ParamsFile string
    end

    methods (TestClassSetup)
        function paths(testCase)
            here = fileparts(mfilename("fullpath"));
            testCase.RepoRoot = string(fileparts(fileparts(fileparts(here))));
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture(fullfile(testCase.RepoRoot, "matlab", "simevents")));

            params = struct( ...
                "inferenceServiceTimeSeconds", struct("p50", 1.0, "p95", 2.0), ...
                "graderServiceTimeSeconds", 30, ...
                "graderCount", 2, ...
                "arrivalsPerDay", 120, ...
                "simulationDays", 0.01, ...
                "reworkRate", 0.12, ...
                "cacheHitRate", 0.05, ...
                "referToReviewFraction", 0.2, ...
                "uploadMegabytes", 4, ...
                "uplinkMbps", 2, ...
                "qualityGateSeconds", 5 ...
                );
            testCase.ParamsFile = string(fullfile(tempdir, "netrasetu_simevents_test_params.json"));
            fid = fopen(testCase.ParamsFile, "w");
            cleaner = onCleanup(@() fclose(fid)); %#ok<NASGU>
            fprintf(fid, "%s", jsonencode(params));
        end
    end

    methods (Test)
        function buildsNamedModel(testCase)
            assumeSimEvents(testCase);
            model = build_district_twin(testCase.ParamsFile);
            testCase.verifyEqual(model, "netrasetu_district_twin");
            testCase.verifyTrue(bdIsLoaded(model));
            testCase.verifyNotEmpty(find_system(model, "SearchDepth", 1, "Type", "block"));
            close_system(model, 0);
        end
    end
end

function assumeSimEvents(testCase)
if isempty(ver("SimEvents"))
    testCase.assumeFail("SimEvents is not available on this runner.");
end
end
