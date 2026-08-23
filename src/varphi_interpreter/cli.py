import typer
import sys
from pathlib import Path
from typing import Optional

app = typer.Typer(add_completion=False)


def version_callback(value: bool):
    if value:
        from . import __version__

        typer.echo(__version__)
        raise typer.Exit()


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    help="Compile and execute a Varphi program.",
)
def main_command(
    ctx: typer.Context,
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the Varphi source file",
    ),
    dap: bool = typer.Option(
        False, "--dap", help="Run in Debug Adapter Protocol mode (for IDEs)."
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable verbose step-by-step logging (Standard mode only).",
    ),
    blank_char: str = typer.Option(
        "_",
        "--blank-char",
        "-b",
        help="Character representing a BLANK cell in input/output (Default: _).",
    ),
    check: bool = typer.Option(
        False, "--check", help="Compile only to verify syntax (does not execute)."
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """
    The Varphi Interpreter.

    Compiles Varphi source code to Python in-memory and executes it immediately.
    Any extra arguments passed after the filename are forwarded to the program
    (e.g., used for setting initial tape values).
    """
    # Select the compiler backend
    if dap:
        from vp2py import VarphiToPythonCompiler
        compiler = VarphiToPythonDAPCompiler()
        compiler.set_source_path(str(input_file))
        if debug:
            typer.echo("Warning: --debug flag is ignored in DAP mode.", err=True)
    else:
        from vp2pydap import VarphiToPythonDAPCompiler
        compiler = VarphiToPythonCompiler()
        if debug:
            compiler.toggle_debug()

    # compile source
    from varphi_devkit import VarphiSyntaxError
    try:
        source_code = input_file.read_text(encoding="utf-8")
        compiled_python_code = compiler.compile(source_code)

        if check:
            typer.echo("OK")
            raise typer.Exit(code=0)

    except VarphiSyntaxError as e:
        typer.echo(f"Compilation Error: {e}", err=True)
        raise typer.Exit(code=1)

    # We construct a new argv.
    # argv[0] should be the script name (we fake it as the input file).
    # We explicitly inject the intercepted --blank-char so the compiled code's argparse catches it.
    # argv[3:] should be the extra arguments passed by the user.
    fake_argv = [str(input_file), "--blank-char", blank_char] + ctx.args

    # Global scope for the executed code.
    execution_globals = {
        "__name__": "__main__",
        "__file__": str(input_file),
        "__builtins__": __builtins__,
    }

    # Interpret the program
    # We create a safe context where sys.argv is temporarily swapped.
    original_argv = sys.argv
    try:
        sys.argv = fake_argv
        exec(compiled_python_code, execution_globals)
    except SystemExit as e:
        raise typer.Exit(code=e.code)
    except Exception as e:
        typer.echo(f"Runtime Error: {e}", err=True)
        raise typer.Exit(code=1)
    finally:
        # Restore sys.argv
        sys.argv = original_argv


def main():
    app()


if __name__ == "__main__":
    main()