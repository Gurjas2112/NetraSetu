classdef tErlangCheck < matlab.unittest.TestCase
    %TERLANGCHECK  Hand-checked Erlang C values for the grader M/M/c stage.

    methods (TestClassSetup)
        function addPaths(testCase)
            here = fileparts(mfilename("fullpath"));
            repo = fileparts(fileparts(fileparts(here)));
            testCase.applyFixture(matlab.unittest.fixtures.PathFixture(fullfile(repo, "matlab", "simevents")));
        end
    end

    methods (Test)
        function matchesHandCalculation(testCase)
            lambda = 3;
            mu = 4;
            c = 2;
            a = lambda / mu;
            rho = a / c;
            testCase.verifyLessThan(rho, 1);

            sum0 = 0;
            for n = 0:c - 1
                sum0 = sum0 + a^n / factorial(n);
            end
            ecTerm = (a^c / factorial(c)) / (1 - rho);
            p0 = 1 / (sum0 + ecTerm);
            pw = ecTerm * p0;
            wq = pw / (c * mu - lambda);
            w = wq + 1 / mu;

            out = erlang_check(lambda, mu, c);
            testCase.verifyEqual(out.stable, true);
            testCase.verifyEqual(out.P0, p0, "AbsTol", 1e-12);
            testCase.verifyEqual(out.Pw, pw, "AbsTol", 1e-12);
            testCase.verifyEqual(out.Wq, wq, "AbsTol", 1e-12);
            testCase.verifyEqual(out.W, w, "AbsTol", 1e-12);
        end

        function unstableWhenOverloaded(testCase)
            out = erlang_check(9, 4, 2);
            testCase.verifyFalse(out.stable);
            testCase.verifyEqual(out.Wq, Inf);
        end
    end
end
