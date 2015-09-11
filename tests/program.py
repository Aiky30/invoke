import os
import sys
from operator import contains, not_

from mock import patch, Mock
from spec import eq_, ok_, skip, trap

from invoke import Program, Collection, main

from _utils import load, cd, IntegrationSpec, expect, skip_if_windows


class Program_(IntegrationSpec):
    class init:
        "__init__"
        def may_specify_version(self):
            eq_(Program(version='1.2.3').version, '1.2.3')

        def default_version_is_unknown(self):
            eq_(Program().version, 'unknown')

        def may_specify_namespace(self):
            foo = load('foo')
            ok_(Program(namespace=foo).namespace is foo)

        def may_specify_name(self):
            eq_(Program(name='Myapp').name, 'Myapp')

        def may_specify_binary(self):
            eq_(Program(binary='myapp').binary, 'myapp')

    class normalize_argv:
        @patch('invoke.program.sys')
        def defaults_to_sys_argv(self, mock_sys):
            argv = ['inv', '--version']
            mock_sys.argv = argv
            p = Program()
            p.print_version = Mock()
            p.run()
            p.print_version.assert_called()

        def uses_a_list_unaltered(self):
            p = Program()
            p.print_version = Mock()
            p.run(['inv', '--version'], exit=False)
            p.print_version.assert_called()

        def splits_a_string(self):
            eq_(Program().normalize_argv("foo bar"), ['foo', 'bar'])

    class normalize_name:
        def defaults_to_capitalized_argv_when_None(self):
            expect("myapp --version", out="Myapp unknown\n", invoke=False)

        def uses_overridden_value_when_given(self):
            p = Program(name='NotInvoke')
            expect("--version", out="NotInvoke unknown\n", program=p)

    class normalize_binary:
        def defaults_to_argv_when_None(self):
            expect(
                "myapp --help",
                out="myapp [--core-opts]",
                invoke=False,
                test=contains
            )

        def uses_overridden_value_when_given(self):
            expect(
                "myapp --help",
                out="nope [--core-opts]",
                program=Program(binary='nope'),
                invoke=False,
                test=contains
            )

        @trap
        def use_binary_basename_when_invoked_absolutely(self):
            Program().run("/usr/local/bin/myapp --help", exit=False)
            stdout = sys.stdout.getvalue()
            ok_("myapp [--core-opts]" in stdout)
            ok_("/usr/local/bin" not in stdout)

    class initial_context:
        def contains_truly_core_arguments_regardless_of_namespace_value(self):
            # Spot check. See integration-style --help tests for full argument
            # checkup.
            for program in (Program(), Program(namespace=Collection())):
                for arg in ('--complete', '--debug', '--warn-only'):
                    expect("--help", program=program, out=arg, test=contains)

        def null_namespace_triggers_task_related_args(self):
            program = Program(namespace=None)
            for arg in Program.task_args:
                expect("--help", program=program, out=arg.name, test=contains)

        def non_null_namespace_does_not_trigger_task_related_args(self):
            program = Program(namespace=Collection())
            # NOTE: have to reverse args because of how contains() works
            not_in = lambda a,b: not_(contains(b, a))
            for arg in Program.task_args:
                expect("--help", out=arg.name, test=not_in)

    class load_collection:
        def complains_when_default_collection_not_found(self):
            # NOTE: assumes system under test has no tasks.py in root. Meh.
            with cd(os.path.abspath(os.path.sep)):
                expect("-l", err="Can't find any collection named 'tasks'!\n")

        def complains_when_explicit_collection_not_found(self):
            expect(
                "-c huhwhat -l",
                err="Can't find any collection named 'huhwhat'!\n",
            )

    class run:
        # NOTE: some of these are integration-style tests, but they are still
        # fast tests (so not needing to go into the integration suite) and
        # touch on transformations to the command line that occur above, or
        # around, the actual parser classes/methods (thus not being suitable
        # for the parser's own unit tests).

        def seeks_and_loads_tasks_module_by_default(self):
            with cd('implicit'):
                expect('foo', out="Hm\n")

        def does_not_seek_tasks_module_if_namespace_was_given(self):
            with cd('implicit'):
                expect(
                    'foo',
                    err="No idea what 'foo' is!\n",
                    program=Program(namespace=Collection('blank'))
                )

        def allows_explicit_task_module_specification(self):
            expect("-c integration print_foo", out="foo\n")

        def handles_task_arguments(self):
            expect("-c integration print_name --name inigo", out="inigo\n")

    class help_:
        "--help"

        class core:
            def empty_invocation_with_no_default_task_prints_help(self):
                expect("-c foo", out="Core options:", test=contains)

            # TODO: On Windows, we don't get a pty, so we don't get a
            # guaranteed terminal size of 80x24. Skip for now, but maybe
            # a suitable fix would be to just strip all whitespace from the
            # returned and expected values before testing. Then terminal
            # size is ignored.
            @skip_if_windows
            def core_help_option_prints_core_help(self):
                # TODO: change dynamically based on parser contents?
                # e.g. no core args == no [--core-opts],
                # no tasks == no task stuff?
                # NOTE: test will trigger default pty size of 80x24, so the
                # below string is formatted appropriately.
                # TODO: add more unit-y tests for specific behaviors:
                # * fill terminal w/ columns + spacing
                # * line-wrap help text in its own column
                expected = """
Usage: inv[oke] [--core-opts] task1 [--task1-opts] ... taskN [--taskN-opts]

Core options:
  --complete                       Print tab-completion candidates for given
                                   parse remainder.
  --no-dedupe                      Disable task deduplication.
  -c STRING, --collection=STRING   Specify collection name to load.
  -d, --debug                      Enable debug output.
  -e, --echo                       Echo executed commands before running.
  -f STRING, --config=STRING       Runtime configuration file to use.
  -h [STRING], --help[=STRING]     Show core or per-task help and exit.
  -H STRING, --hide=STRING         Set default value of run()'s 'hide' kwarg.
  -l, --list                       List available tasks.
  -p, --pty                        Use a pty when executing shell commands.
  -r STRING, --root=STRING         Change root directory used for finding task
                                   modules.
  -V, --version                    Show version and exit.
  -w, --warn-only                  Warn, instead of failing, when shell
                                   commands fail.

""".lstrip()
                for flag in ['-h', '--help']:
                    expect(flag, out=expected, program=main.program)

        class per_task:
            "per-task"
            def prints_help_for_task_only(self):
                expected = """
Usage: invoke [--core-opts] punch [--options] [other tasks here ...]

Docstring:
  none

Options:
  -h STRING, --why=STRING   Motive
  -w STRING, --who=STRING   Who to punch

""".lstrip()
                for flag in ['-h', '--help']:
                    expect('-c decorator {0} punch'.format(flag), out=expected)

            def works_for_unparameterized_tasks(self):
                expected = """
Usage: invoke [--core-opts] biz [other tasks here ...]

Docstring:
  none

Options:
  none

""".lstrip()
                expect('-c decorator -h biz', out=expected)

            def honors_program_binary(self):
                expect(
                    '-c decorator -h biz',
                    out="Usage: notinvoke",
                    test=contains,
                    program=Program(binary='notinvoke')
                )

            def displays_docstrings_if_given(self):
                expected = """
Usage: invoke [--core-opts] foo [other tasks here ...]

Docstring:
  Foo the bar.

Options:
  none

""".lstrip()
                expect('-c decorator -h foo', out=expected)

            def dedents_correctly(self):
                expected = """
Usage: invoke [--core-opts] foo2 [other tasks here ...]

Docstring:
  Foo the bar:

    example code

  Added in 1.0

Options:
  none

""".lstrip()
                expect('-c decorator -h foo2', out=expected)

            def dedents_correctly_for_alt_docstring_style(self):
                expected = """
Usage: invoke [--core-opts] foo3 [other tasks here ...]

Docstring:
  Foo the other bar:

    example code

  Added in 1.1

Options:
  none

""".lstrip()
                expect('-c decorator -h foo3', out=expected)
