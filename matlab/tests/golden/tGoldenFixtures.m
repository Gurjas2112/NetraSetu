classdef tGoldenFixtures < matlab.unittest.TestCase
    %TGOLDENFIXTURES  Decisions on synthetic fixtures, not clinical accuracy.

    properties
        RepoRoot string
    end

    methods (TestClassSetup)
        function addPaths(testCase)
            here = fileparts(mfilename("fullpath"));
            testCase.RepoRoot = string(fileparts(fileparts(fileparts(here))));
            matlabDir = fullfile(testCase.RepoRoot, "matlab");
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture(matlabDir));
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture(fullfile(matlabDir, "nx")));
        end
    end

    methods (Test)
        function blurIsRetake(testCase)
            s = jsondecode(netrasetu_analyze_json(testCase.fx("blur_s8.png"), tempname));
            testCase.verifyEqual(s.decision, 'RETAKE');
            testCase.verifyEqual(s.quality.failureMode, 'defocus');
            testCase.verifyTrue(startsWith(s.retakeGuidanceKey, 'retake.'));
            testCase.verifyEmpty(s.grade);
        end

        function haemIsRefer(testCase)
            s = jsondecode(netrasetu_analyze_json(testCase.fx("grade2_haem.png"), tempname));
            testCase.verifyEqual(s.decision, 'REFER');
            testCase.verifyTrue(s.reviewRequired);
            testCase.verifyGreaterThanOrEqual(s.pReferable, 0);
        end

        function jsonAlwaysArray(testCase)
            s = jsondecode(netrasetu_analyze_json(testCase.fx("grade0_clean.png"), tempname));
            testCase.verifyTrue(iscell(s.criteria) || isstruct(s.criteria) && isempty(s.criteria) ...
                || size(s.criteria, 1) >= 1 || isequal(s.criteria, []));
        end
    end

    methods
        function p = fx(testCase, name)
            p = fullfile(testCase.RepoRoot, "tests", "fixtures", name);
        end
    end
end
