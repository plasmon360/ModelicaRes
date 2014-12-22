#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Context managers to be used as simulators

In general, the context managers are used like this:

.. code-block:: python

   >>> with context_manager() as simulator: # doctest: +SKIP
   ...     simulator.run(model1, params1)
   ...     simulator.run(model2, params2)
   ...     # ...

For more details, see the documentation for the context managers below:

- :class:`dymola_script` - Write a Dymola\ :sup:`®`-formatted script

- :class:`dymosim` - Run executable models from Dymola\ :sup:`®`

- :class:`fmi` - Simulate FMUs_ via PyFMI_


.. _FMUs: https://www.fmi-standard.org/
.. _PyFMI: http://www.pyfmi.org/
"""
__author__ = "Kevin Davies and Arnout Aertgeerts"
__email__ = "kdavies4@gmail.com"
__copyright__ = ("Copyright 2012-2014, Kevin Davies, Hawaii Natural Energy "
                 "Institute, and Georgia Tech Research Corporation")
__license__ = "BSD-compatible (see LICENSE.txt)"

import os
import sys
import subprocess
import pyfmi

from datetime import date
from shutil import copy, move
from . import ParamDict, read_options, read_params, write_options, write_params
from ..util import expand_path, run_in_dir

# OS-dependent strings
EXE = '.exe' if os.name == 'nt' else '' # File extension for an executable
EXEC_PREFIX = '' if os.name == 'nt' else './' # Prefix to execute a file


class dymola_script(object):

    """Context manager to write a Dymola\ :sup:`®`-formatted script

    **Initialization parameters (defaults in parentheses):**

    - *fname* ("run_sims.mos"): Name of the script file to be written, relative
      to the current directory

    - *command* ('simulateModel'): Simulation or other command to
      Dymola\ :sup:`®`

         Besides 'simulateModel', this can be 'linearizeModel' to create a state
         space representation or 'translateModel' to create executables without
         running them.

    - *working_dir* (''): Working directory where the executable, log files,
      etc. are initially created (relative to the current directory)

         '~' may be included to represent the user directory.

    - *results* (['dsin.txt', 'dsfinal.txt', 'dslog.txt', 'dsres.mat',
      'dymolalg.txt', 'dymosim%x']): List of files to copy to the results folder

         Each entry is the name or path of a file that is generated by the
         command.  The path is relative to *working_dir*.  '%x' may be included
         in the name to represent '.exe' if the operating system is Windows and
         '' otherwise.  The result folders are named by the run number and
         placed within the folder contains the script (*fname*).

    - *packages* ([]): List of Modelica_ packages that should be preloaded or
      scripts that should be run before the experiments

         Each may be a "\*.mo" file, a folder that contains a "package.mo" file,
         or a "\*.mos" file.  The path may be absolute or relative to
         *working_dir*.  The Modelica Standard Library does not need to be
         included since it is loaded automatically.  If an entry is a script
         ("\*.mos"), it is run from its folder.

    - *\*\*options*: Additional keyword arguments for *command*

         Any option with a value of *None* will be skipped.

         These arguments can also be added, modified, or removed after
         initialization.  Please see Example 2 below.

         If *command* is 'simulateModel', then the following keywords may be
         used.  The defaults (in parentheses) are applied by Dymola\ :sup:`®`,
         not by this context manager.

         - *startTime* (0): Start of simulation

         - *stopTime* (1): End of simulation

         - *numberOfIntervals* (0): Number of output points

         - *outputInterval* (0): Distance between output points

         - *method* ("Dassl"): Integration method

         - *tolerance* (0.0001): Tolerance of integration

         - *fixedstepsize* (0): Fixed step size for Euler

         - *resultFile* ("dsres.mat"): Where to store result

    **Example 1 (a single simulation):**

    .. code-block:: python

       >>> from modelicares.exps.simulators import dymola_script

       >>> with dymola_script("examples/ChuaCircuit/run_sims1.mos", stopTime=2500) as simulator: # doctest: +ELLIPSIS
       ...     simulator.run('Modelica.Electrical.Analog.Examples.ChuaCircuit')
       Starting to write the Dymola script...
       Run 1:  simulateModel(...)
       Finished writing the Dymola script.

    This generates a summary of the runs in *examples/ChuaCircuit/runs.tsv*:

    ===== ============= ============= ===============================================
    Run # Command       Options       Model & parameters
    ===== ============= ============= ===============================================
    1     simulateModel stopTime=2500 Modelica.Electrical.Analog.Examples.ChuaCircuit
    ===== ============= ============= ===============================================

    and the following script in *examples/ChuaCircuit/run_sims1.mos*:

    .. code-block:: modelica

       // Dymola script written by ModelicaRes...
       import Modelica.Utilities.Files.copy;
       import Modelica.Utilities.Files.createDirectory;
       Advanced.TranslationInCommandLog = true "Also include translation log in command log";
       cd("...");
       destination = ".../examples/ChuaCircuit/";

       // Run 1
       ok = simulateModel(problem="Modelica.Electrical.Analog.Examples.ChuaCircuit", stopTime=2500);
       if ok then
           savelog();
           dest = destination + "1/";
           createDirectory(dest);
           copy("dsin.txt", dest + "dsin.txt", true);
           copy("dslog.txt", dest + "dslog.txt", true);
           copy("dsres.mat", dest + "dsres.mat", true);
           copy("dymosim", dest + "dymosim...", true);
           copy("dymolalg.txt", dest + "dymolalg.txt", true);
       end if;
       clearlog();

       exit();

    where ``...`` depends on the local system.

    **Example 2 (simulating with different options):**

    The command options can also be modified or removed after establishing the
    context:

    .. code-block:: python

       >>> from modelicares.exps.simulators import dymola_script

       >>> with dymola_script("examples/ChuaCircuit/run_sims2.mos", stopTime=250) as simulator: # doctest: +ELLIPSIS
       ...     simulator.run('Modelica.Electrical.Analog.Examples.ChuaCircuit', stopTime=2500)
       ...     simulator.run('Modelica.Electrical.Analog.Examples.ChuaCircuit')
       ...     del simulator.stopTime
       ...     simulator.run('Modelica.Electrical.Analog.Examples.ChuaCircuit')
       ...     simulator.stopTime = 25
       ...     simulator.run('Modelica.Electrical.Analog.Examples.ChuaCircuit')
       Starting to write the Dymola script...
       Run 1:  simulateModel(...)
       Run 2:  simulateModel(...)
       ...
       Finished writing the Dymola script.

    Initially the stop time is set at 250 s, but in the first run it is
    temporarily overwritten to 2500 s.  In the second run, it falls back to its
    initial setting.  The stop time is removed before the third run and then set
    to 25 s for the final run.

    This generates the following table:

    ===== ============= ============= ===============================================
    Run # Command       Options       Model & parameters
    ===== ============= ============= ===============================================
    1     simulateModel stopTime=2500 Modelica.Electrical.Analog.Examples.ChuaCircuit
    2     simulateModel stopTime=250  Modelica.Electrical.Analog.Examples.ChuaCircuit
    3     simulateModel               Modelica.Electrical.Analog.Examples.ChuaCircuit
    4     simulateModel stopTime=25   Modelica.Electrical.Analog.Examples.ChuaCircuit
    ===== ============= ============= ===============================================

    and a corresponding script in *examples/ChuaCircuit/run_sims2.mos*.

    **Example 3 (full-factorial design of experiments):**

    Multiple parameters can be adjusted using functions from the
    :mod:`~modelicares.exps.doe` module.

    .. code-block:: python

       >>> from modelicares.exps.simulators import dymola_script
       >>> from modelicares import doe

       >>> with dymola_script("examples/ChuaCircuit/run_sims3.mos") as simulator: # doctest: +ELLIPSIS
       ...     for params in doe.fullfact({'C1.C': [8, 10], 'L.L': [18, 20]}):
       ...         simulator.run("Modelica.Electrical.Analog.Examples.ChuaCircuit", params=params)
       Starting to write the Dymola script...
       Run 1:  simulateModel(...)
       ...
       Run 4:  simulateModel(...)
       Finished writing the Dymola script.

    This generates the following table:

    ===== ============= ======= ==================================================================
    Run # Command       Options Model & parameters
    ===== ============= ======= ==================================================================
    1     simulateModel         Modelica.Electrical.Analog.Examples.ChuaCircuit(C1(C=8), L(L=18))
    2     simulateModel         Modelica.Electrical.Analog.Examples.ChuaCircuit(C1(C=10), L(L=18))
    3     simulateModel         Modelica.Electrical.Analog.Examples.ChuaCircuit(C1(C=8), L(L=20))
    4     simulateModel         Modelica.Electrical.Analog.Examples.ChuaCircuit(C1(C=10), L(L=20))
    ===== ============= ======= ==================================================================

    and a corresponding script in *examples/ChuaCircuit/run_sims3.mos*.


    .. _Modelica: http://www.modelica.org/
    """

    def __init__(self, fname="run_sims.mos", command='simulateModel',
                 working_dir='',
                 results=['dsin.txt', 'dsfinal.txt', 'dslog.txt', 'dsres.mat',
                          'dymolalg.txt', 'dymosim%x'],
                 packages=[], **options):
        """Upon initialization, start writing the script.

        See the top-level class documentation.
        """

        # Pre-process and store the arguments.
        fname = expand_path(fname)
        self._command = command
        working_dir = expand_path(working_dir)
        results_dir = os.path.dirname(fname)
        for i, result in enumerate(results):
            results[i] = result.replace('%x', EXE)
        self._results = results
        self._options = options

        # Open the script.
        print("Starting to write the Dymola script...")
        mos = open(fname, 'w')
        self._mos = mos

        # Write the header.
        mos.write('// Dymola script written by ModelicaRes %s\n'
                  % date.isoformat(date.today()))
        mos.write('import Modelica.Utilities.Files.copy;\n')
        mos.write('import Modelica.Utilities.Files.createDirectory;\n')
        mos.write('Advanced.TranslationInCommandLog = true "Also include '
                  'translation log in command log";\n')
        mos.write('cd("%s");\n' % working_dir)
        for package in packages:
            if package.endswith('.mos'):
                mos.write('cd("%s");\n' % os.path.dirname(package))
                mos.write('RunScript("%s");\n' % os.path.basename(package))
            else:
                if package.endswith('.mo'):
                    mos.write('openModel("%s");\n' % package)
                else:
                    mos.write('openModel("%s");\n' % os.path.join(package,
                                                                  'package.mo'))
            mos.write('cd("%s");\n' % working_dir)
        mos.write('destination = "%s";\n\n'
                  % (os.path.normpath(results_dir) + os.path.sep))
        # Sometimes Dymola opens with an error; simulate any model to clear the
        # error.
        # mos.write('simulateModel("Modelica.Electrical.Analog.Examples.'
        #           'ChuaCircuit");\n\n')

        # Start the run log.
        run_log = open(os.path.join(results_dir, "runs.tsv"), 'w')
        run_log.write("Run #\tCommand\tOptions\tModel & parameters\n")
        self._run_log = run_log

        # Start counting the run() calls.
        self.n_runs = 0

    def __delattr__(self, attr):
        """Delete a command option.
        """
        del self._options[attr]

    def __getattr__(self, attr):
        """If an unknown attribute is requested, look for it in the dictionary
        of command options.
        """
        return self._options[attr]

    def __setattr__(self, attr, value):
        """Add known attributes directly, but unknown attributes go to the
        dictionary of command options.
        """
        if attr in ('_command', '_results', '_options', 'n_runs', '_run_log',
                    '_mos'):
            object.__setattr__(self, attr, value) # Traditional method
        else:
            self._options[attr] = value

    def __enter__(self):
        """Enter the context of the simulator.
        """
        # Everything has been done in __init__, so just do this:
        return self

    def __exit__(self, *exc_details):
        """Exit the context of the simulator.
        """
        # Write the command to exit the simulation environment.
        # Otherwise, the script will hang until it's closed manually.
        self._mos.write("exit();\n")
        self._mos.close()

        self._run_log.close()
        print("Finished writing the Dymola script.")

    def run(self, model=None, params={}, **options):
        """Write commands to run and save the results of a single experiment.

        **Parameters:**

        - *model*: String representing the name of the model, including the
          full Modelica_ path (in dot notation)

             If *model* is *None*, then the model is not included in the
             command.  Dymola\ :sup:`®` will use the last translated model.

        - *params*: Dictionary of parameter names and values to be set within
          the model

             The keys or variable names in this dictionary must indicate the
             hierarchy within the model---either in Modelica_ dot ('.') notation
             or via nested dictionaries.  If *model* is *None*, then *params* is
             ignored.  Python_ values are automatically represented in Modelica_
             syntax (see :meth:`~modelicares.exps.ParamDict.__str__`).
             Redeclarations and other prefixes must be included in the keys
             along with the class names (e.g.,
             ``params={'redeclare package Medium': 'Modelica.Media.Air.MoistAir'}``).

             Any item with a value of *None* is skipped.

        - *\*\*options*: Additional or modified keyword arguments for the
          command chosen upon initialization (see the top-level documentation of
          this context manager, :class:`dymola_script`)

             Any option with a value of *None* will be skipped.

             These are applied only for the current run.  They override the
             options given at initialization or set via attribute access.

        Please see the examples in the top-level documentation of
        :class:`dymola_script`.
        """

        # Increment the number of runs and retrieve some attributes.
        self.n_runs += 1
        n_runs = self.n_runs
        mos = self._mos
        command = self._command
        opts = self._options.copy()
        opts.update(options)

        # Write the command to run the model.
        mos.write('// Run %i\n' % n_runs)
        problem = '"%s%s"' % (model, ParamDict(params)) if model else None
        call = '%s%s' % (command, ParamDict(opts, problem=problem))
        mos.write('ok = %s;\n' % call)

        # Write commands to save the results and clear Dymola's log file.
        mos.write('if ok then\n')
        mos.write('    savelog();\n')
        mos.write('    dest = destination + "%s%s";\n' % (n_runs, os.path.sep))
        mos.write('    createDirectory(dest);\n')
        for result in self._results:
            mos.write('    copy("%s", dest + "%s", true);\n' %
                      (result, result))
        mos.write('end if;\n')
        mos.write('clearlog();\n\n')

        # Add an entry to the run log.
        self._run_log.write('\t'.join([str(n_runs),
                                       command,
                                       str(ParamDict(opts))[1:-1],
                                       problem[1:-1] if problem else ''])
                            + '\n')
        print('Run %s:  %s' % (n_runs, call))

    # TODO:
    # def continue_run(self):


class dymosim(object):

    """Context manager to run executable models from Dymola\ :sup:`®`

    **Initialization parameters (defaults in parentheses):**

    - *command* ('-s'): Simulation or other action command to dymosim.

         Besides '-s', this can be '-l' to create a state space representation.

    - *results_dir* (''): Directory in which to store the results, relative to
      the current directory

    - *results* (['dslog.txt']): List of result files to keep, besides the
      trajectory (dsres.mat), initial values (dsin.txt), and final values
      (dsfinal.txt)

         Each entry is the name or path of a file that is generated by the
         executable.  The path is relative to the directory of the model (see
         :meth:`run`).

    - *\*\*options*: Adjustments to the simulation settings under "Experiment
      parameters", "Method tuning parameters", and "Output parameters" in the
      initialization file (e.g., dsin.txt)

         See the initialization file for more information.  The common
         parameters are those under "Experiment parameters".  Note that they are
         slightly different than those for :class:`dymola_script`:

         - *StartTime* (compare to *startTime*): Time at which integration
           starts

         - *StopTime* (compare to  *stopTime*): Time at which integration stops

         - *Increment* (compare to *outputInterval*): Communication step size,
           if > 0

         - *nInterval* (compare to *numberOfIntervals*): Number of communication
           intervals, if > 0

         - *Tolerance* (compare to *tolerance*): Relative precision of signals
           for simulation

         - *MaxFixedStep* (compare to *fixedstepsize*): Maximum step size of
           fixed step size integrators, if > 0.0

         - *Algorithm* (compare to *method*): Integration algorithm (accepts an
           integer instead of a string)

         Any option with a value of *None* will be skipped.

         These arguments can also be added, modified, or removed after
         initialization.  Please see Example 2 of :class:`dymola_script`; the
         same approach can be used with this context manager, :class:`dymosim`.

    The results are placed in *results_dir* in subfolders named by the run
    number.  Within each subfolder, the files in the *results* list as well as
    the trajectory (dsres.mat) and initial values (dsin.txt) are renamed with
    the period number just before the file extension.  The :meth:`run` method
    creates period number 1 and :meth:`continue_run` continues with 2, 3, etc.
    The final values (dsfinal.txt) are those of the last period and are copied
    directly.

    **Example:**

    .. code-block:: python

       >>> from modelicares.exps.simulators import dymosim

       >>> with dymosim(StopTime=2500) as simulator: # doctest: +ELLIPSIS
       ...     simulator.run('examples/ChuaCircuit/dymosim')

    Notice that this is similar to Example 1 of :class:`dymola_script`.
    Likewise, the form of Examples 2 and 3 for that context manager holds for
    this one.
    """

    def __init__(self, command='-s', results_dir='', results=['dslog.txt'],
                 **options):
        """Upon initialization, establish some settings.

        See the top-level class documentation.
        """

        # Pre-process and store the arguments.
        self._command = command
        self._results_dir = expand_path(results_dir)
        self._results = results
        self._options = options

        # Start the run log.
        run_log = open(os.path.join(results_dir, "runs.tsv"), 'w')
        run_log.write("Run #\tPeriod #\tOptions\tExecutable\tInitial values & parameters\n")
        self._run_log = run_log

        # Start counting the run() calls.
        self.n_runs = 0

    def __delattr__(self, attr):
        """Delete a command option.
        """
        del self._options[attr]

    def __getattr__(self, attr):
        """If an unknown attribute is requested, look for it in the dictionary
        of command options.
        """
        return self._options[attr]

    def __setattr__(self, attr, value):
        """Add known attributes directly, but unknown attributes go to the
        dictionary of command options.
        """
        if attr in ('_command', '_results_dir', '_results', '_options',
                    'n_runs', '_n_periods', '_run_log', '_current_model'):
            object.__setattr__(self, attr, value) # Traditional method
        else:
            self._options[attr] = value

    def __enter__(self):
        """Enter the context of the simulator.
        """
        # Everything has been done in __init__, so just do this:
        return self

    def __exit__(self, *exc_details):
        """Exit the context of the simulator.
        """
        self._run_log.close()

    def _paths(self, model=None):
        """Given a model's path (*model*, without extension) and the internal
        state, return a tuple of:
        1. the model's directory
        2. the model's base name (without directory or extension)
        3. the model executable (with '.exe' added in Windows)
        4. the results directory
        5. the path to the initialization file

        Also, confirm that the executable exists.

        Save the model.  If *model* is None, use the last model.
        """

        # Determine some paths and directories.
        if model is None:
            model = self._current_model
        else:
            self._current_model = model
        model_dir, model_base = os.path.split(model)
        results_dir = os.path.join(self._results_dir, str(self.n_runs))
        dsin_path = os.path.join(results_dir, 'dsin%i.txt' % self._n_periods)

        # Locate the executable.
        executable = model_base + EXE
        assert os.path.isfile(model + EXE), (
            'The exectuable (%s) cannot be found in the "%s" folder.'
            % (executable, os.path.abspath(model_dir)))

        return model_dir, model_base, executable, results_dir, dsin_path

    def _run(self, executable, params, options, model_dir, results_dir,
             dsin_path):
        """Write the given model parameters and initial values (*params*) and
        simulation options (*options*) to the initialization file at
        *dsin_path*, run *executable* in directory *model_dir*, and save the
        results to *results_dir*.

        Also write to the log file.
        """
        # Determine the file locations.
        dsres_path = os.path.join(results_dir, 'dsres%i.mat' % self._n_periods)
        dsfinal_path = os.path.join(results_dir, 'dsfinal.txt')

        # Write the simulation options.
        opts = self._options.copy()
        opts.update(options)
        write_options(opts, dsin_path)

        # Write the model parameters and initial conditions.
        write_params(params, dsin_path)

        # Run the model.
        run_in_dir([EXEC_PREFIX + executable, self._command, '-f', dsfinal_path,
                    dsin_path, dsres_path], model_dir)

        # Copy the other results.
        for result in self._results:
            source = os.path.join(model_dir, result)
            destination = os.path.join(results_dir,
                str(self._n_periods).join(os.path.splitext(result)))
            copy(source, destination)

        # Add an entry to the run log.
        self._run_log.write('\t'.join([str(self.n_runs),
                                       str(self._n_periods),
                                       str(ParamDict(options))[1:-1],
                                       executable,
                                       str(ParamDict(params))[1:-1]])
                            + '\n')

    def run(self, model='dymosim', params={}, **options):
        r"""Run and save the results of a single experiment.

        **Parameters:**

        - *model*: String representing the directory and base name of the model
          executable

             '.exe' will be added if the operating system is Windows.

             The initialization file is expected at *model* + '_dsin.txt'.
             However, if the base name (without directory) is 'dymosim', then
             'dsin.txt' will be used instead from the same directory.  If the
             initialization file does not exist, it will be created.

             If *model* is *None*, then the previous model will be used.

        - *params*: Dictionary of names and values of parameters and variables
          with tunable initial values to be set within the model

             The keys or variable names in this dictionary must indicate the
             hierarchy within the model---either in Modelica_ dot ('.') notation
             or via nested dictionaries.  Due to the format of the
             initialization files, arrays must be broken into scalars by
             indicating the indices (Modelica_ 1-based indexing) in the key
             along with the variable name.  Also, enumerations and Booleans must
             be given as their unsigned integer equivalents (e.g., 0 for
             *False*).  Strings and prefixes are not supported.

             Any item with a value of *None* is skipped.

       - *\*\*options*: Adjustments to the simulation settings under "Experiment
         parameters", "Method tuning parameters", and "Output parameters" in the
         initialization file

             Any option with a value of *None* will be skipped.

             For more common parameters, see the initialization parameters in
             the top-level documentation of this context manager,
             :class:`dymosim`.

             These are applied only for the current run.  They override the
             options given at initialization or set via attribute access.

        Please see the example in the top-level documentation of
        :class:`dymosim`.
        """
        # Increment the number of runs and reset the number of periods.
        self.n_runs += 1
        self._n_periods = 1

        # Determine the file locations.
        model_dir, model_base, exe, results_dir, dsin_path = self._paths(model)

        # Locate the original dsin file.
        if model_base == 'dymosim':
            dsin_name = 'dsin.txt'
        else:
            dsin_name = model_base + '_dsin.txt'
        if not os.path.isfile(os.path.join(model_dir, dsin_name)):
            run_in_dir([EXEC_PREFIX + exe, '-i', dsin_name], model_dir)
        orig_dsin_path = os.path.join(model_dir, dsin_name)

        # Create the results folder and copy the original dsin file into it.
        if not os.path.isdir(results_dir):
            os.makedirs(results_dir)
        copy(orig_dsin_path, dsin_path)

        # Write the parameters and options, run the model, and save the results.
        self._run(exe, params, options, model_dir, results_dir, dsin_path)

    def continue_run(self, duration, params={}, **options):
        """Continue the last run (using the same model).

        **Parameters:**

        - *duration*: Number of additional seconds to simulate

        - *params*: Dictionary of names and values of parameters to be adjusted
          within the model

             By default, the parameters remain as they were in the last
             :meth:`run`.  See that method for details on *params*.

       - *\*\*options*: Adjustments to the simulation settings under "Experiment
         parameters", "Method tuning parameters", and "Output parameters" in the
         initialization file

            By default, the options remain as they were in the last :meth:`run`.
            See that method for details.

            StartTime and StopTime are ignored because they are determined
            automatically from *duration* and the stop time of the last
            simulation.

        .. warning::

           Be careful not to use *params* to adjust variables with tunable
           initial values.  Otherwise, the new simulation will not continue
           where the last one left off.
        """
        # Increment the number of periods.
        self._n_periods += 1

        # Determine the file locations.
        model_dir, __, exe, results_dir, dsin_path = self._paths()

        # The new initialization file is the old final values file.
        move(os.path.join(results_dir, 'dsfinal.txt'), dsin_path)

        # Set the new stop time.
        start_time = read_options('StartTime', dsin_path)
        options['StartTime'] = start_time
        options['StopTime'] = start_time + duration

        # Write the parameters and options, run the model, and save the results.
        self._run(exe, params, options, model_dir, results_dir, dsin_path)


class fmi(object):

    """Context manager to simulate FMUs_ via PyFMI_

    .. Warning:: This context manager has not been implemented yet.

    **Example:**

    .. code-block:: python

       >>> from modelicares.exps.simulators import fmi

       >>> with fmi(stopTime=2500) as simulator:
       ...     simulator.run('examples/ChuaCircuit.fmu')

    For more complicated scenarios, use the same form as in examples 2 and 3
    in the :class:`dymola_script` documentation.
    """

    def __init__(self,
                 working_dir=None,
                 results_dir=None,
                 result=None,
                 fmu_options={},
                 **options):
        """Upon initialization, establish some settings.

        See the top-level class documentation.
        """

        if working_dir is None:
            working_dir = os.getcwd()
        else:
            working_dir = expand_path(working_dir)

        self._working_dir = working_dir
        self._results_dir = results_dir
        self._result = os.path.join(results_dir, result)
        self._fmu_options = fmu_options

        # Start counting the run() calls.
        self.n_runs = 0

    def load(self, model):
        """
        Load the FMU for continued simulation in the continue_run method.
        """

        fmu = pyfmi.load_fmu(model)
        fmu.initialize()

        return fmu

    def run(self, model, start_time, stop_time, params={}):
        r"""Run and save the results of a single experiment.

        .. Warning:: This function has not been implemented yet.
        """
        self.n_runs += 1

        fmu = self.load(model)

        options = fmu.simulate_options()

        for key, value in self._fmu_options:
            options[key] = value

        options['initialize'] = False
        if self._result:
            options['result_file_name'] = self._result + str(self.n_runs) + '.txt'
        else:
            options['result_file_name'] = model + str(self.n_runs) + '.txt'

        return (fmu.simulate(
            start_time=int(start_time),
            final_time=int(stop_time),
            options=options
        ), fmu)

    def continue_run(self, fmu, duration, params={}):
        start_time = fmu.time

        options = fmu.simulate_options()
        options['initialize'] = False
        if self._result:
            options['result_file_name'] = self._result + str(self.n_runs) + '.txt'
        else:
            options['result_file_name'] = fmu.get_name() + str(self.n_runs) + '.txt'

        return (fmu.simulate(
            start_time=start_time,
            final_time=int(start_time+duration),
            options=options
        ), fmu)

if __name__ == '__main__':
    # Test the contents of this file.

    import doctest
    doctest.testmod()