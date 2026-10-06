classdef ContractStubTest < matlab.unittest.TestCase
    %CONTRACTSTUBTEST  The engine boundary returns JSON text that decodes into contract 1.1.

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
        function returnsCharJson(testCase)
            txt = netrasetu_analyze_json(testCase.fixture("grade2_haem.png"), tempname);
            testCase.verifyClass(txt, "char");
            testCase.verifyEqual(size(txt, 1), 1);
        end

        function decodesToContract(testCase)
            s = jsondecode(netrasetu_analyze_json(testCase.fixture("grade2_haem.png"), tempname));
            testCase.verifyEqual(s.contractVersion, '1.1');
            testCase.verifyTrue(ismember(s.decision, {'REFER', 'ROUTINE', 'RETAKE'}));
            testCase.verifyNumElements(s.posterior, 5);
            testCase.verifyEqual(sum(s.posterior), 1, "AbsTol", 1e-6);
            testCase.verifyEqual(s.pReferable, sum(s.posterior(3:5)), "AbsTol", 1e-9);
            testCase.verifyTrue(startsWith(s.cfgHash, 'sha256:'));
        end

        function stubNeverSendsHome(testCase)
            s = jsondecode(netrasetu_analyze_json(testCase.fixture("grade0_clean.png"), tempname));
            testCase.verifyEqual(s.decision, 'REFER');
            testCase.verifyTrue(s.reviewRequired);
        end
    end

    methods
        function p = fixture(testCase, name)
            p = fullfile(testCase.RepoRoot, "tests", "fixtures", name);
        end
    end
end
