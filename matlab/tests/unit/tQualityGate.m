classdef tQualityGate < matlab.unittest.TestCase
    %TQUALITYGATE  The quality gate rejects known defocus at σ = 4, 8 and 12.

    properties
        RepoRoot string
        Clean string
    end

    properties (TestParameter)
        sigma = {4, 8, 12};
    end

    methods (TestClassSetup)
        function addPaths(testCase)
            here = fileparts(mfilename("fullpath"));
            testCase.RepoRoot = string(fileparts(fileparts(fileparts(here))));
            matlabDir = fullfile(testCase.RepoRoot, "matlab");
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture(matlabDir));
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture(fullfile(matlabDir, "nx")));
            testCase.Clean = fullfile(testCase.RepoRoot, "tests", "fixtures", "grade0_clean.png");
        end
    end

    methods (Test)
        function rejectsDefocus(testCase, sigma)
            I = imread(testCase.Clean);
            p = fullfile(tempdir, sprintf("nx_blur_%d.png", sigma));
            imwrite(imgaussfilt(im2double(I), sigma), p);
            q = nx_quality(p);
            testCase.verifyEqual(string(q.verdict), "reject");
            testCase.verifyEqual(string(q.failureMode), "defocus");
        end

        function rejectsUnderexposedFixture(testCase)
            p = fullfile(testCase.RepoRoot, "tests", "fixtures", "underexposed.png");
            q = nx_quality(p);
            testCase.verifyEqual(string(q.verdict), "reject");
            testCase.verifyEqual(string(q.failureMode), "underexposed");
        end

        function rejectsPartialFovFixture(testCase)
            p = fullfile(testCase.RepoRoot, "tests", "fixtures", "partial_fov.png");
            q = nx_quality(p);
            testCase.verifyEqual(string(q.verdict), "reject");
            testCase.verifyEqual(string(q.failureMode), "partial_fov");
        end

        function acceptsCleanFixture(testCase)
            q = nx_quality(testCase.Clean);
            testCase.verifyNotEqual(string(q.verdict), "reject");
            testCase.verifyEqual(string(q.failureMode), "none");
        end
    end
end
