Table des matières
------------------

-   [1 README contents](#sec-1)
    -   [1.1 On Windows or other non-Unix systems](#sec-1-1)
    -   [1.2 On Unix or Linux systems](#sec-1-2)
    -   [1.3 Reporting problems](#sec-1-3)

1 README contents
-----------------

Pynits is a tool which I find useful while editing Python source code
with Vim, for tidying up individual sources lines. It is particularily
helpful when formatting lines holding long or complex expressions.

The documentation is kept in file
[pynits.txt](http://fp-etc/pynits-doc.html), which you may browse or
print, yet it is meant for the Vim help system. Once the installation is
completed as per the steps described below, and from within Vim, you may
quickly get back to the documentation through the command::

~~~~ {.example}
:help pynits
~~~~

Pynits messages are also available in French, given the **LANG**
environment variable is `fr` or a variant of `fr`, before you call Vim.

### 1.1 On Windows or other non-Unix systems

You likeley have fetched a [recent **.zip**
archive](https://github.com/pinard/Pynits/zipball/master). Choose the
directory where you want the files installed. This is normally one of
the directories listed by VIM command:

~~~~ {.example}
:set runtimepath
~~~~

Let's call it *DIRECTORY*. Create *DIRECTORY* if it does not exist and
unzip the distribution you got into *DIRECTORY*. For making the
documentation available to VIM, execute VIM commands:

~~~~ {.example}
:helptags DIRECTORY/doc
~~~~

replacing *DIRECTORY* in the command above, of course.

You have to manage in such a way that Python will successfully import
file `python/pynits.py`. One way is changing your Python installation so
it will look in that directory. See your Python documentation for
knowing where the directory `site-packages/` is, then add these lines to
file `.../site-packages/sitecustomize.py`:

~~~~ {.src .src-python}
import sys
sys.path.append('DIRECTORY/python')
~~~~

once again replacing *DIRECTORY* as appropriate, above. Another way is
to move the just installed file `python/pynits.py` into another
directory on the Python import search path. Pick a directory among those
Python lists when you interactively execute:

~~~~ {.src .src-python}
import sys
print sys.path
~~~~

A third way might be to preset **PYTHONPATH** in the environment so this
variable points to `DIRECTORY/python`.

Finally, you should edit file `DIRECTORY/ftplugin/python.vim` — create
such a file if it does not exist already — and make sure it holds at
least the following line:

~~~~ {.example}
python import pynits
~~~~

### 1.2 On Unix or Linux systems

On Linux or other Unix systems, you might follow the instructions above,
meant for non-Unix systems, they should work for Unix systems as well.
Or else, you may fetch a [recent **.tar.gz**
archive](https://github.com/pinard/FP-etc/tarball/master). You may
either install this tool for yourself only, or for all users in your
system.

-   Personal installation\

    This tool may be installed for yourself only, and this might be your
    only choice if you do not have super-user privileges. Merely type
    **make install-user** from the unpacked Pynits distribution. As a
    separate step, your `~/.vimrc` file should be modified, or created
    if necessary, so it holds the following lines:

~~~~ {.example}
if has('python')
  python <<EOF
import os, sys
sys.path.append(os.path.expanduser('~/.vim/python'))
EOF
endif
~~~~

-   System wide installation\

    If you have super-user privileges, this tool may be installed
    system-wide, for all users. Before doing so, you have to find out
    what is the **VIM** value for your installation. Within Vim, ask:

~~~~ {.example}
:echo $VIM
~~~~

    Let's presume the listed value is *DIRECTORY*. Then within a shell,
    execute the following command:

~~~~ {.src .src-sh}
make install-root VIM=DIRECTORY
~~~~

    This will use `$VIM/vimfiles/`, which is the standard location for
    local site additions. If you do not like this choice, then modify
    file Makefile as you see fit.

    You also have to manage so Python will know how to import modules
    from the `$VIM/vimfiles/python/` subdirectory. You may find a few
    hints about how to do this by looking at the last half of the
    section \`On Windows and other non-Unix systems\`, above.

### 1.3 Reporting problems

Email to [François Pinard](mailto:pinard@iro.umontreal.ca) for reporting
documentation or execution bugs, or for sharing suggestions.
