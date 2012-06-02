#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright © 2004, 2005 Progiciels Bourbeau-Pinard inc.
# François Pinard <pinard@iro.umontreal.ca>, 2004.

"""\
A few supplementary tools for Python support within Vim.

This script may also be used as a program, rather than imported within
Vim, mainly for debugging purposes.  The first Python line of FILE is
read and reformatted on standard output, the remainder of FILE is ignored.

Usage: pynits.py [OPTION]... [FILE]

Operation mode:
  -h   Print this help and exit.
  -d   Enable debugging trace.
  -P   Enable code profiling.

Enabling heuristics:
  -b   Columnar formatting, no refilling.
  -c   Columnar formatting, with refilling.
  -l   Format all on a single line, `-w' ignored.
  -p   Full formatting, no refilling.
  -q   Full formatting, with refilling (default).

Formatting options:
  -w WIDTH   Line width in columns (default is 80).
  -i STEP    Indentation step in columns (default is 4).

If FILE is not specified, standard input is read.
"""

__metaclass__ = type
import gettext, os, re, sys

try:
    import vim
except ImportError:
    class vim:
        class error(Exception): pass
        class current:
            buffer = []
            class window: cursor = 1, 0
        def eval(text):
            return {'&shiftwidth': str(Editor.indentation),
                    '&textwidth': str(Editor.limit)}[text]
        eval = staticmethod(eval)
        def command(text): pass
        command = staticmethod(command)

localedir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'locale')
try:
    _ = gettext.translation('pynits', localedir).gettext
except IOError:
    def _(text): return text

def declare_ordinals(*names):
    # Declare, within the caller's scope, enumeration variables from NAMES,
    # starting with value 0.  Such integer variables print their own name.
    # Return that precise type containing nothing but these new variables.

    class Ordinal(int):

        def __new__(cls, name, value):
            return int.__new__(cls, value)

        def __init__(self, name, value):
            self.name = name

        def __repr__(self):
            return self.name

        def __str__(self):
            return self.name

    locals = sys._getframe(1).f_locals
    for value, name in enumerate(names):
        locals[name] = Ordinal(name, value)
    return Ordinal

class Main:
    def __init__(self):
        self.command = None

    def main(self, *arguments):
        profiling = False
        import getopt
        options, arguments = getopt.getopt(arguments, 'Pbcdhi:lpqw:')
        for option, value in options:
            if option == '-P':
                profiling = True
            elif option == '-b':
                self.command = layout_engine.column_layout
            elif option == '-c':
                self.command = layout_engine.column_fill_layout
            elif option == '-d':
                Editor.debugging = True
            elif option == '-i':
                Editor.indentation = int(value)
            elif option == '-h':
                sys.stdout.write(_(__doc__))
                sys.exit(0)
            elif option == '-l':
                self.command = layout_engine.line_layout
            elif option == '-p':
                self.command = layout_engine.retract_layout
            elif option == '-q':
                self.command = layout_engine.retract_fill_layout
            elif option == '-w':
                Editor.limit = int(value)
        assert len(arguments) < 2, arguments
        if arguments:
            file_ = file(arguments[0])
        else:
            file_ = sys.stdin
        if self.command is None:
            self.command = layout_engine.retract_fill_layout
        vim.current.buffer[:] = file_.read().splitlines()
        if profiling:
            import profile, pstats
            profile.run('run.command(\'n\')', '.profile-data')
            sys.stderr.write('\n')
            stats = pstats.Stats('.profile-data')
            stats.strip_dirs().sort_stats('time', 'cumulative').print_stats(10)
        else:
            self.command('n')
            sys.stderr.write('\n')
        for line in vim.current.buffer[:current_cursor()[0]]:
            sys.stdout.write(line + '\n')

def install_vim():
    # FIXME: I'm unable to use neither `,s' nor `,t': strange!
    # FIXME: Unexplained delay for commands `,c' and `,m'.
    register_local_keys(
        'pynits',
        (('<LocalLeader><LocalLeader>', 'n', 'find_nit'),
         ('<LocalLeader>"', 'n', 'force_double_quotes'),
         ('<LocalLeader>\'', 'n', 'force_single_quotes'),
         ('<LocalLeader>(', 'n', 'add_parentheses'),
         ('<LocalLeader>)', 'n', 'remove_parentheses'),
         ('<LocalLeader>.', 'n', 'correct_nit'),
         ('<LocalLeader>b', 'n', 'column_layout'),
         ('<LocalLeader>c', 'n', 'column_fill_layout'),
         ('<LocalLeader>d', 'n', 'choose_debug'),
         ('<LocalLeader>f', 'n', 'choose_filling_tool'),
         ('<LocalLeader>l', 'n', 'line_layout'),
         ('<LocalLeader>p', 'n', 'retract_layout'),
         ('<LocalLeader>q', 'n', 'retract_fill_layout'),
         ('<LocalLeader>y', 'n', 'show_syntax'),
         ('Q', 'n', 'retract_fill_layout')))
    Editor.indentation = int(vim.eval('&shiftwidth'))
    Editor.limit = int(vim.eval('&textwidth')) or 80

def register_local_keys(plugin, triplets):
    for keys, modes, name in triplets:
        for mode in modes:
            python_command = ':python %s.%s(\'%s\')' % (plugin, name, mode)
            sid_name = '<SID>%s_%s' % (mode, name)
            plug_name = '<Plug>%s_%s_%s' % (plugin.capitalize(), mode, name)
            vim.command('%smap <buffer> %s %s' % (mode, keys, plug_name))
            vim.command('%snoremap <buffer> <script> %s %s'
                        % (mode, plug_name, sid_name))
            if mode == 'i':
                vim.command('%snoremap <buffer> <silent> %s <C-O>%s<CR>'
                            % (mode, sid_name, python_command))
            else:
                vim.command('%snoremap <buffer> <silent> %s %s<CR>'
                            % (mode, sid_name, python_command))

def adjust_coding():
    if vim.eval('&filetype') != 'python':
        return
    coding = vim.eval('&fileencoding') or vim.eval('&encoding')
    substitutions = {'latin1': 'ISO-8859-1'}
    coding = substitutions.get(coding, coding).lower()
    buffer = vim.current.buffer
    for index in 0, 1:
        if index < len(buffer):
            line = buffer[index]
            # Theoretically: coding[=:]\s*([-\w-.]+)
            match = re.match(r'(#.*?-\*-.*coding: *)([-_A-Za-z0-9]*)(.*)',
                             line)
            if match:
                line = match.expand(r'\1%s\3' % coding)
                if line != buffer[index]:
                    buffer[index] = line
                return
    index = 0
    if index < len(buffer) and buffer[index].startswith('#!'):
        index = 1
    buffer[index:index] = ['# -*- coding: %s -*-' % coding]

## Syntax control layout.

import compiler, compiler.ast, compiler.consts, compiler.visitor

# Dummy syntaxic nodes for representing a few Python code helpers.
# The PATCH attribute inhibits the production of `pass'.
class Elif(compiler.ast.If):
    patch = True
class Else(compiler.ast.Pass):
    patch = True
class Except(compiler.ast.Tuple):
    patch = True
class Finally(compiler.ast.Pass):
    patch = True
class Try(compiler.ast.Pass):
    patch = True

class Layout_Engine:

    # Line limit when backward exploring to find the start of a logical
    # Python line.
    backward_limit = 12

    # Line limit when forward exploring to find the end of a logical Python
    # line.
    forward_limit = 200

    # Tool for filling comments.
    filling_tool_choices = 'fmt', 'par', 'vim', 'python'
    filling_tool = 'fmt'

    def show_syntax(self, mode):
        # Print the syntax of a line (to help debugging).
        row = current_cursor()[0]
        try:
            start, end, margin, comments, tree = self.find_python_line(
                row)
        except SyntaxError, diagnostic:
            sys.stderr.write(str(diagnostic))
        else:
            sys.stdout.write(str(tree))

    def line_layout(self, mode):
        Editor.strategy = LINE
        self.process_line(None)

    def column_layout(self, mode):
        Editor.strategy = COLUMN
        self.process_line(False)

    def column_fill_layout(self, mode):
        Editor.strategy = COLUMN
        self.process_line(True)

    def retract_layout(self, mode):
        Editor.strategy = RETRACT
        self.process_line(False)

    def retract_fill_layout(self, mode):
        Editor.strategy = RETRACT
        self.process_line(True)

    def process_line(self, fill):
        # Reformat the line and FILL if requested.
        row = current_cursor()[0]
        buffer = vim.current.buffer
        line = buffer[row].lstrip()
        if line.startswith('#'):
            end = self.process_comment(row)
        elif line:
            end = self.process_python_code(row, fill)
        else:
            end = self.process_white(row)
        # Move cursor to the following line.
        if end <= len(buffer):
            column = left_margin(buffer[end-1])
        else:
            end = len(buffer)
            column = 0
        try:
            change_current_cursor(end, column)
        except vim.error:
            # FIXME: Vim error while formatting, for example, `x = 0.0'.
            pass

    def process_white(self, row):
        start = end = row
        buffer = vim.current.buffer
        if '\f' in buffer[row]:
            insertion = '\f\n'
        else:
            insertion = '\n'
        while start > 1 and not buffer[start-2].lstrip():
            start -= 1
            if '\f' in buffer[start-1]:
                insertion = '\f\n'
        while end < len(buffer) and not buffer[end].lstrip():
            end += 1
            if '\f' in buffer[end-1]:
                insertion = '\f\n'
        return self.alter_buffer(start, end + 1, insertion)

    def process_comment(self, row):
        start = end = row
        buffer = vim.current.buffer
        prefix = ' '*left_margin(buffer[row]) + '#'
        while start > 1 and buffer[start-2].startswith(prefix):
            start -= 1
        while end < len(buffer) and buffer[end].startswith(prefix):
            end += 1
        if self.filling_tool == 'vim':
            vim.command('normal %dGgq%dG' % (start, end))
            return current_cursor()[0]
        if self.filling_tool == 'fmt':
            import os, tempfile
            name = tempfile.mktemp()
            file(name, 'w').writelines([buffer[row] + '\n'
                                       for row in range(start, end + 1)])
            insertion = (os.popen('fmt -u -w%d -p\'%s\' <%s'
                                  % (Editor.limit, prefix + ' ', name))
                         .read)()
            os.remove(name)
        elif self.filling_tool == 'par':
            import os, tempfile
            name = tempfile.mktemp()
            file(name, 'w').writelines([buffer[row] + '\n'
                                       for row in range(start, end + 1)])
            # FIXME: See PARINIT and decide if it should be integrated.
            insertion = os.popen('par w%d <%s' % (Editor.limit, name)).read()
            os.remove(name)
        elif self.filling_tool == 'python':
            import textwrap
            lines = [buffer[row][len(prefix):]
                      for row in range(start, end + 1)]
            insertion = textwrap.fill(textwrap.dedent('\n'.join(lines)),
                                      width=Editor.limit,
                                      fix_sentence_endings=True,
                                      initial_indent=prefix + ' ',
                                      subsequent_indent=prefix + ' ')
        return self.alter_buffer(start, end + 1, insertion)

    def process_python_code(self, row, fill):
        try:
            start, end, margin, comments, tree = self.find_python_line(
                row)
        except SyntaxError, diagnostic:
            sys.stderr.write(str(diagnostic))
            return row
        editor = Editor(margin, fill)
        try:
            compiler.walk(tree, editor,
                          walker=compiler.visitor.ExampleASTVisitor(),
                          verbose=True)
        except Dead_End, diagnostic:
            if not fill:
                sys.stderr.write('%s...' % str(diagnostic))
                return row
            editor = Editor(margin, False)
            try:
                compiler.walk(tree, editor,
                              walker=compiler.visitor.ExampleASTVisitor(),
                              verbose=True)
            except Dead_End, diagnostic2:
                sys.stderr.write('%s...' % str(diagnostic))
                return row
            sys.stderr.write(_("I ought to disable filling."))
        result = str(editor)
        if result.endswith(':\n'):
            result += self.recomment(margin + editor.indentation,
                                         comments)
        else:
            result = self.recomment(margin, comments) + result
        return self.alter_buffer(start, end, result)

    def find_python_line(self, row):
        # Read Python code starting at given ROW or, for getting a correct
        # syntax, up to a dozen earlier lines.  Return (START, END, MARGIN,
        # COMMENTS, TREE), stating the first and last row for the found
        # Python code, the margin width, a list of comment fragments in that
        # code, and a syntax tree for that code.
        start = row
        while True:
            try:
                end, margin, comments, text = self.read_python_line(start)
                # Looking back enough, one may find some valid Python code,
                # but if that code does not reach current line, we probably
                # have to move back even further.
                if end <= row:
                    raise SyntaxError(
                        _("Syntax error, maybe did not back up enough?"))
                if text.endswith(':\n'):
                    for prefix in 'class ', 'def ', 'if ', 'for ', 'while ':
                        if text.startswith(prefix):
                            patch = True
                            text = text[:-2].rstrip() + ': pass\n'
                            break
                    else:
                        for prefix, class_ in (('try:', Try),
                                                ('else:', Else),
                                                ('finally:', Finally)):
                            if text.startswith(prefix):
                                patch = class_
                                text = 'pass'
                                break
                        else:
                            if text.startswith('elif '):
                                text = text[2:-2].rstrip() + ': pass\n'
                                patch = Elif
                            elif text == 'except:\n':
                                text = '()'
                                patch = Except
                            elif text.startswith('except '):
                                text = text[7:-2].strip() + ',\n'
                                patch = Except
                            else:
                                patch = None
                else:
                    patch = None
                from parser import ParserError
                try:
                    tree = compiler.parse(text)
                except ParserError, diagnostic:
                    raise SyntaxError(diagnostic)
            except SyntaxError:
                # If any syntax error, the physical line is likely not the
                # first of the logical line.  We then attempt the analysis
                # moving back one physical line, but yet, not more than a
                # dozen times.
                if start < 1 or start <= row - self.backward_limit:
                    raise
                start -= 1
            else:
                # At last, we got a usable syntax tree.
                break
        if patch:
            assert isinstance(tree, compiler.ast.Module), tree
            assert isinstance(tree.node, compiler.ast.Stmt), tree.node
            assert len(tree.node.nodes) == 1, tree.node.nodes
            node = tree.node.nodes[0]
            if patch is True:
                # We got class, def, if, for or while.  PATCH is for
                # inhibiting the production of a `pass' statement.
                node.patch = True
            elif isinstance(node, compiler.ast.Pass):
                # We got try, else or finally.
                tree.node.nodes[0] = patch()
            elif isinstance(node, compiler.ast.If):
                # We got elif.
                tree.node.nodes[0] = patch(node.tests, node.else_)
            else:
                # We got except.
                assert isinstance(node, compiler.ast.Discard), node
                assert isinstance(node.expr, compiler.ast.Tuple), node.expr
                node.expr = patch(node.expr.nodes)
        return start, end, margin, comments, tree

    def read_python_line(self, row):
        # Read Python code starting at given ROW, reading continuation lines
        # as needed.  Return (END, MARGIN, COMMENTS, TEXT), giving the line
        # after the found statement, the margin width, a list of comment
        # fragments found within Python code, then the full text of the
        # Python code as a single string, newlines included, yet without
        # the initial margin nor comments.
        start = row
        buffer = vim.current.buffer
        line = buffer[row].rstrip()
        margin = left_margin(line)
        comments = []
        lines = []
        stack = []
        line = line.lstrip()
        something = False
        while True:
            lines.append(line)
            while line:
                if line[0] in '([{':
                    something = True
                    stack.append({'(': ')', '[': ']', '{': '}'}[line[0]])
                    line = line[1:].lstrip()
                    continue
                if line[0] in ')]}':
                    something = True
                    if not stack:
                        raise SyntaxError(_("Spurious `%s'.") % line[0])
                    expected = stack.pop()
                    if line[0] != expected:
                        raise SyntaxError(_("`%s' seen, `%s' expected!")
                                          % (line[0], expected))
                    line = line[1:].lstrip()
                    continue
                if line.startswith('#'):
                    lines[-1] = lines[-1][:-len(line)].rstrip()
                    if line.startswith('# '):
                        comments.append(line[2:])
                    else:
                        comments.append(line[1:])
                    break
                if line == '\\':
                    if row >= len(buffer):
                        break
                    row += 1
                    line = buffer[row].lstrip()
                    lines.append(line)
                    continue
                match = re.match(r'u?r?(\'\'\'|""")', line)
                if match:
                    something = True
                    terminator = match.group(1)
                    line = line[match.end():]
                    while terminator not in line:
                        if (row - start == self.forward_limit
                              or row + 1 >= len(buffer)):
                            line = None
                            break
                        row += 1
                        line = buffer[row].rstrip()
                        lines.append(line)
                    else:
                        position = line.find(terminator)
                        line = line[position+3:].lstrip()
                    continue
                match = re.match(r'u?r?(\'([^\\\']+|\\.)*\'|"([^\\"]+|\\.)*")',
                                 line)
                if match:
                    something = True
                    line = line[match.end():].lstrip()
                    continue
                line = line[1:].lstrip()
                something = True
            if not stack and something:
                break
            if len(lines) == self.forward_limit or row + 1 >= len(buffer):
                if stack:
                    raise SyntaxError(_("`%s' expected!")
                                      % '\', `'.join(stack[::-1]))
                raise SyntaxError(_("No Python code!"))
            row += 1
            line = buffer[row].strip()
        return (start + len(lines), margin, comments,
                '\n'.join(lines) + '\n')

    def recomment(self, margin, comments):
        while comments:
            if not comments[-1]:
                del comments[-1]
            elif not comments[0]:
                del comments[0]
            else:
                break
        if comments:
            if comments[-1][-1] not in '.!?':
                comments[-1] += '.'
            while len(comments) > 1 and not comments[0]:
                comments.pop(0)
            if comments[0][0].islower():
                comments[0] = (comments[0][0].upper()
                                   + comments[0][1:])
        lines = []
        for comment in comments:
            if comment:
                lines.append(' '*margin + '# ' + comment + '\n')
            else:
                lines.append(' '*margin + '#\n')
        return ''.join(lines)

    def alter_buffer(self, start, end, text):
        lines = text.splitlines()
        buffer = vim.current.buffer
        if end - start != len(lines) or buffer[start:end] != lines:
            buffer[start:end] = lines
        return start + len(lines)

layout_engine = Layout_Engine()
show_syntax = layout_engine.show_syntax
line_layout = layout_engine.line_layout
column_layout = layout_engine.column_layout
column_fill_layout = layout_engine.column_fill_layout
retract_layout = layout_engine.retract_layout
retract_fill_layout = layout_engine.retract_fill_layout

## Editing tool for a syntax tree.

declare_ordinals('NOT_ASSOC', 'LEFT_ASSOC', 'RIGHT_ASSOC')

def prepare_editor():
    # This function changes structural classes in `compiler.ast', adding
    # notions of priority and associativity and also, sometimes, the string
    # represeting the operator.  These informations are quite useful, for
    # example, to decide when and how parentheses should be inserted while
    # reconstructing the surface of a Python statement.
    for infos in (
            (0, NOT_ASSOC, 'AssTuple', 'Tuple'),
            (1, NOT_ASSOC, 'Lambda'),
            (2, LEFT_ASSOC, ('Or', 'or')),
            (3, LEFT_ASSOC, ('And', 'and')),
            (4, NOT_ASSOC, ('Not', 'not')),
            (5, LEFT_ASSOC, 'Compare'),
            (6, LEFT_ASSOC, ('Bitor', '|')),
            (7, LEFT_ASSOC, ('Bitxor', '^')),
            (8, LEFT_ASSOC, ('Bitand', '&')),
            (9, LEFT_ASSOC, ('LeftShift', '<<'), ('RightShift', '>>')),
            (10, LEFT_ASSOC, ('Add', '+'), ('Sub', '-')),
            (11, LEFT_ASSOC, ('Div', '/'), ('FloorDiv', '//'), ('Mod', '%'),
                               ('Mul', '*')),
            (12, RIGHT_ASSOC, ('Power', '**')),
            (13, NOT_ASSOC, ('Invert', '~'), ('UnaryAdd', '+'),
                            ('UnarySub', '-')),
            (14, LEFT_ASSOC, 'AssAttr', 'AssList', 'CallFunc', 'Getattr',
                               'Slice', 'Subscript'),
            (15, NOT_ASSOC, 'AssName', 'Backquote', 'Const', 'Dict', 'List',
                            'ListComp', 'Name'),
            ):
        priority = infos[0]
        associativity = infos[1]
        for pair in infos[2:]:
            if isinstance(pair, tuple):
                class_name, operator = pair
            else:
                class_name = pair
                operator = None
            class_ = getattr(compiler.ast, class_name)
            setattr(class_, 'priority', priority)
            setattr(class_, 'associativity', associativity)
            setattr(class_, 'operator', operator)

prepare_editor()

# Priority outside any expression, or immediately within parentheses meant
# for priority or splitting.
STATEMENT_PRIORITY = -1
# Priority within a tuple.  Also the priorty whenever a new tuple ought to
# be nested within parentheses.
TUPLE_PRIORITY = 0
# Up to that priority, a space is guaranteed on either side of operators.
# For higher priorities, spaces are decided by the SPACING variable.
PRIORITE_SPACING = 6
# Priority of phenomenons like function call, indexing or attribute selection.
# These phenomenons are left associative between them, parentheses are
# suppressed directly in the EDIT function.
CALL_PRIORITY = 14

# Enumeration for various layout strategies.  Keep in order!
declare_ordinals('LINE', 'COLUMN', 'RETRACT')

# For when a layout attempt gets into a logical dead-end.
class Dead_End(Exception):
    pass

# A few special characters used withint debuggin output.
CENTERED_DOT = '·'
PARAGRAPH_SIGN = '¶'

class Editor:
    # An EDITOR behaves like a syntactic "visitor" for the `compile' module.
    # It knows how to obey formats and progressively accumulates the surface
    # structure while it is being constructed.  Moreover, it manages a
    # continuation mechanism which is triggered by dead ends.

    # Debugging is rather verbose.
    debugging = False

    # Margin increase per idnentation step.
    indentation = 4

    # Lines are ideally kept within 80 columns by default.
    limit = 80

    # The maximal strategy, limiting the layout strategies.
    strategy = RETRACT

    # REWRITE_WITHOUT notes a few stylistic improvements locally requested
    # by the user, yet inactive by default.  They bear the slight risk of
    # modifying the semantic of the rewritten result.  Possible members are
    # 'apply', 'find', 'has_key', 'print' and 'string'.
    rewrite_without = []

    def __init__(self, margin, fill):
        # BLOCKS is a list of line blocks.  Each block is a string holding
        # one or more strings, including line terminators.  Any block having
        # more than one line may not participate in a refilling.
        self.blocks = []
        # LINE gives the number of completed or started lines.
        self.line = 0
        # COLUMN gives the number of columns in last line.
        self.column = 0
        # MARGINS is a stack of margins.  Each margin gives the number of
        # spaces at the beginnining of any new line.
        self.margins = [margin]
        # SLACKS is a stack of slacks.  Each slack gives a number of needed
        # free columns on the last produced line, a kind of supplementary
        # right margin.
        self.slacks = [0]
        # FILL is TRUE when produced lines should be refilled until a margin
        # change, False or None otherwise.  The None value also means that
        # there is no maximum column.
        self.fill = fill
        # STARTS is a stack of starts.  Each start is the block number from
        # which a filling will occur.
        self.starts = []
        # Recursion level in EDIT calls, for tracing purposes.
        self.depth_level = 0
        # Current nesting of explicit parentheses.
        self.nesting = 0
        # PRIORITIES is a stack of priorities.  A priority qualifies the
        # text being currenly generated.
        self.priorities = [STATEMENT_PRIORITY]
        # ENONCE_DEL flags a `del' statement.  The `del` keyword is aready written.
        self.del_statement = False
        # MARGINS2 is a stack of second margins.  Each second margin
        # establishes a supplementary minimum for the margin.  See the EDIT
        # function documentation for more details.
        self.margins2 = [None]
        # SPACINGS is a stack of spacings.  Each spacing controls the possible
        # sparing of some spaces.  See the EDIT function documentation for
        # more details.
        self.spacings = [2]
        # ECONOMY may trigger the sparing of a parentheses pair.  See the
        # EDIT function documentation for more details.
        self.economy = False
        # STRATEGIES is a stack of strategies.  Each strategy is being tried
        # at a particular nesting level.
        self.strategies = [LINE]

    def __str__(self):
        return ('\n'.join([line.rstrip(' ')
                           for line in ''.join(self.blocks).splitlines()])
                + '\n')

    def debug_format(self, format, arguments, position, index):
        if Editor.debugging:
            frame = sys._getframe()
            while True:
                frame = frame.f_back
                name = frame.f_code.co_name
                for prefix in 'visit', 'operator_':
                    if name.startswith(prefix):
                        break
                else:
                    continue
                break
            self.debug_text((format[:position].replace('%', '')
                              + CENTERED_DOT
                              + format[position:].replace('%', '')),
                             *((name[len(prefix):] + ':',) + arguments[:index]
                               + (CENTERED_DOT,) + arguments[index:]))

    def debug_text(self, *arguments):
        if Editor.debugging:
            self.debug(*arguments)
            if self.blocks:
                sys.stdout.write(''.join(self.blocks) + PARAGRAPH_SIGN + '\n')

    def debug(self, *arguments):
        if Editor.debugging:
            write = sys.stdout.write
            write('%-16s' % ('%2d %d,%s,%d %d%s'
                             % (self.priorities[-1],
                                self.margins[-1], self.margins2[-1] or '',
                                self.slacks[-1], self.spacings[-1],
                                ('', '-')[self.economy])))
            write('%*d' % (-self.depth_level, self.depth_level))
            assert self.strategies[0] == LINE, self.strategies
            if len(self.strategies) > 1:
                write(' ')
                write(''.join([str(strategy)[0]
                               for strategy in self.strategies[1:]]))
            for argument in arguments:
                write(' ')
                if argument is None:
                    write('-')
                elif isinstance(argument, str):
                    if len(argument) > 16:
                        write(argument[:13] + '...')
                    else:
                        write(argument)
                elif isinstance(argument, compiler.ast.Node):
                    write(argument.__class__.__name__)
                else:
                    write(repr(argument))
            write('\n')

    ## Statements.

    def visitAssert(self, node):
        format = 'assert%#'
        arguments = [TUPLE_PRIORITY]
        if node.fail is None:
            format += ' %^'
            arguments += [node.test]
        else:
            format += ' %(%!%^%|%), %^'
            arguments += [None, node.test, node.fail]
        self.process(format, *arguments)

    def visitAssign(self, node):
        format = ''
        arguments = []
        for left in node.nodes:
            format += '%(%^%|%) = '
            arguments += [None, left]
        format += '%(%!%^%)'
        arguments += [None, node.expr]
        self.process(format, *arguments)

    def visitAugAssign(self, node):
        self.process('%(%^%|%) %s %(%!%^%)', None, node.node, node.op, None,
                     node.expr)

    def visitBreak(self, node):
        self.process('break')

    def visitContinue(self, node):
        self.process('continue')

    def visitDiscard(self, node):
        self.process('%^', node.expr)

    def visitElif(self, node):
        assert len(node.tests) == 1, node.tests
        for test, statement in node.tests:
            self.process('elif %;%^%:', test)
            self.process_body(node, statement)
        assert node.else_ is None, node.else_

    def visitElse(self, node):
        self.process('else:')

    def visitExcept(self, node):
        if len(node.nodes) == 0:
            self.process('except:')
        elif len(node.nodes) == 1:
            self.process('except %;%^%:', node.nodes[0])
        else:
            self.process('except %;%^%:', compiler.ast.Tuple(node.nodes))

    def visitExec(self, node):
        format = 'exec%#'
        arguments = [TUPLE_PRIORITY]
        if node.globals is None:
            if node.locals is None:
                format += ' %^'
                arguments += [node.expr]
            else:
                format += ' %(%!%^%|%) in %^'
                arguments += [None, node.expr, node.locals]
        else:
            format += ' %(%!%^%|%) in %(%!%^%|%), %^'
            arguments += [None, node.expr, None, node.locals, node.globals]
        self.process(format, *arguments)

    def visitFinally(self, node):
        self.process('finally:')

    def visitFor(self, node):
        self.process('for %;%^ in %^%:', node.assign, node.list)
        self.process_body(node, node.body)
        assert node.else_ is None, node.else_

    def visitFrom(self, node):
        format = 'from %s import'
        arguments = [node.modname]
        separator = ' '
        for name, alias in node.names:
            format += separator + '%s'
            arguments += [name]
            if alias is not None:
                format += ' alias %s'
                arguments += [alias]
            separator = ', '
        self.process(format, *arguments)

    def visitGlobal(self, node):
        format = 'global'
        arguments = []
        separator = ' '
        for name in node.names:
            format += separator + '%s'
            arguments += [name]
            separator = ', '
        self.process(format, *arguments)

    def visitIf(self, node):
        separator = 'if'
        assert len(node.tests) == 1, node.tests
        for test, statement in node.tests:
            self.process('%s %;%^%:', separator, test)
            self.process_body(node, statement)
            separator = 'elif'
        assert node.else_ is None, node.else_

    def visitImport(self, node):
        format = 'import'
        arguments = []
        separator = ' '
        for name, alias in node.names:
            format += separator + '%s'
            arguments += [name]
            if alias is not None:
                format += ' as %s'
                arguments += [alias]
            separator = ', '
        self.process(format, *arguments)

    def visitPass(self, node):
        self.process('pass')

    def visitPrint(self, node):
        self.process_print(node, False)

    def visitPrintnl(self, node):
        self.process_print(node, True)

    def visitRaise(self, node):
        format = 'raise%#'
        arguments = [TUPLE_PRIORITY]
        if node.expr3 is None:
            if node.expr2 is None:
                if node.expr1 is not None:
                    format += ' %^'
                    arguments += [node.expr1]
            else:
                format += ' %(%!%^%|%), %^'
                arguments += [None, node.expr1, node.expr2]
        else:
            format = ' %(%!%^%|%), %(%!%^%|%), %^'
            arguments += [None, node.expr1, None, node.expr2, node.expr3]
        self.process(format, *arguments)

    def visitReturn(self, node):
        if is_none(node.value):
            format = 'return'
            arguments = []
        else:
            format = 'return %^'
            arguments = [node.value]
        self.process(format, *arguments)

    def visitTry(self, node):
        self.process('try:')

    def visitTryExcept(self, node):
        # body, handlers, else_
        assert False

    def visiTryFinally(self):
        assert False

    def visitWhile(self, node):
        self.process('while %;%^%:', node.test)
        self.process_body(node, node.body)
        assert node.else_ is None, node.else_

    def visitYield(self, node):
        self.process('yield %^', node.value)

    ## Expressions.

    def unary_operator(self, node):
        operator = node.operator
        if operator.isalpha():
            format = '%(%s %^%)'
        else:
            format = '%(%s%^%)'
        self.spacings[-1] -= 1
        self.process(format, node.priority, operator, node.expr)
        self.spacings[-1] += 1

    def binary_operator(self, node):
        priority = node.priority
        if node.associativity == RIGHT_ASSOC:
            format = '%(%(%^%_%|%s%_'
            arguments = [priority, None, node.left, node.operator]
            node = node.right
            while node == priority:
                format += '%^%_%|%s%_'
                arguments += [node.left, node.operator]
                node = node.right
            format += '%^%)%)'
            arguments += [node]
        else:
            pairs = []
            while node.priority == priority:
                pairs.append((node.operator, node.right))
                node = node.left
            pairs.reverse()
            format = '%(%(%^'
            arguments = [priority, None, node]
            for operator, expression in pairs:
                format += '%_%|%s%_%^'
                arguments += [operator, expression]
            format += '%)%)'
        self.spacings[-1] -= 1
        self.process(format, *arguments)
        self.spacings[-1] += 1

    def masking_operator(self, node):
        self.spacings[-1] -= 1
        self.multiple_operator(node)
        self.spacings[-1] += 1

    def multiple_operator(self, node):
        format = '%(%(%^'
        arguments = [node.priority, None, node.nodes[0]]
        for expression in node.nodes[1:]:
            if node.operator.isalpha():
                format += ' %|%s %^'
            else:
                format += '%_%|%s%_%^'
            arguments += [node.operator, expression]
        format += '%)%)'
        self.process(format, *arguments)

    visitAdd = binary_operator
    visitAnd = multiple_operator

    def visitBackquote(self, node):
        self.process('repr(%^)', node.expr)

    visitBitand = masking_operator
    visitBitor = masking_operator
    visitBitxor = masking_operator

    def visitCallFunc(self, node):
        if (self.rewrite_without_apply(node) or self.rewrite_without_has_key(node)
              or self.rewrite_without_string(node)):
            return
        count = (len(node.args) + bool(node.star_args)
                  + bool(node.dstar_args))
        if count == 0:
            self.process('%(%^()%)', node.priority, node.node)
            return
        format = '%!%(%^(%\\'
        arguments = [node.priority, node.node, TUPLE_PRIORITY]
        if count == 1:
            format += '%!'
        separator = ''
        for expression in node.args:
            format += separator + '%^'
            arguments += [expression]
            separator = ', %|'
        if node.star_args is not None:
            format += separator + '*%^'
            arguments += [node.star_args]
            separator = ', %|'
        if node.dstar_args is not None:
            format += separator + '**%^'
            arguments += [node.dstar_args]
        format += ')%)%/'
        self.process(format, *arguments)

    def visitCompare(self, node):
        if self.rewrite_without_find(node):
            return
        format = '%(%^'
        arguments = [node.priority, node.expr]
        for operator, comparand in node.ops:
            if operator.isalpha():
                format += ' %|%s %^'
            else:
                format += '%_%|%s%_%^'
            arguments += [operator, comparand]
        format += '%)'
        self.process(format, *arguments)

    def visitConst(self, node):
        if isinstance(node.value, str):
            self.process_string(node.value)
        elif isinstance(node.value, (int, float)):
            self.process_constant(node.value)
        else:
            assert False, (type(node.value), node.value)

    def visitDict(self, node):
        format = '%!%({%\\'
        arguments = [node.priority, TUPLE_PRIORITY]
        separator = ''
        for key, value in node.items:
            format += separator + '%^: %^'
            arguments += [key, value]
            separator = ', %|'
        format += '}%)%/'
        self.process(format, *arguments)

    visitDiv = binary_operator
    visitFloorDiv = binary_operator

    def visitGetattr(self, node):
        attributes = [node.attrname]
        node = node.expr
        while isinstance(node, compiler.ast.Getattr):
            attributes.append(node.attrname)
            node = node.expr
        attributes.reverse()
        self.process('%(%^' + '%|.%s'*len(attributes) + '%)', node.priority,
                     node, *attributes)

    visitInvert = unary_operator

    def visitLambda(self, node):
        flags = node.flags
        usuals = node.argnames[:]
        if node.kwargs:
            assert flags & compiler.consts.CO_VARKEYWORDS, flags
            flags &= ~compiler.consts.CO_VARKEYWORDS
            dstar_args = usuals.pop()
        else:
            dstar_args = None
        if node.varargs:
            assert flags & compiler.consts.CO_VARARGS, flags
            flags &= ~compiler.consts.CO_VARARGS
            star_args = usuals.pop()
        else:
            star_args = None
        assert not flags, flags
        if node.defaults:
            keys = usuals[-len(node.defaults):]
            usuals = usuals[:-len(node.defaults)]
        format = '%(lambda'
        arguments = [node.priority]
        separator = ' '
        for usual in usuals:
            format += separator + '%s'
            arguments += [usual]
            separator = ', %|'
        if node.defaults:
            for key, value in zip(keys, node.defaults):
                format += separator + '%s=%^'
                arguments += [key, value]
                separator = ', %|'
        if star_args is not None:
            format += separator + '*%s'
            arguments += [star_args]
            separator = ', %|'
        if dstar_args is not None:
            format += separator + '**%s'
            arguments += [dstar_args]
        format += ': %^%)'
        arguments += [node.code]
        self.process(format, *arguments)

    visitLeftShift = binary_operator

    def visitList(self, node):
        format = '%!%([%\\'
        if len(node.nodes) == 1:
            format += '%!'
        arguments = [CALL_PRIORITY, TUPLE_PRIORITY]
        separator = ''
        for expression in node.nodes:
            format += separator + '%^'
            arguments += [expression]
            separator = ', %|'
        format += ']%)%/'
        self.process(format, *arguments)

    def visitListComp(self, node):
        self.process(r'%!%([%\%^' + '%^'*len(node.quals) + ']%)%/',
                     CALL_PRIORITY, TUPLE_PRIORITY, node.expr, *node.quals)

    visitMod = binary_operator
    visitMul = binary_operator

    def visitName(self, node):
        self.process('%s', node.name)

    visitNot = unary_operator
    visitOr = multiple_operator
    visitPower = binary_operator
    visitRightShift = binary_operator

    def visitSlice(self, node):
        format = self.maybe_del(node) + '%^%!%([%\\'
        arguments = [node.expr, node.priority, STATEMENT_PRIORITY]
        if node.lower is not None:
            format += '%|%^'
            arguments += [node.lower]
        format += '%|:'
        if node.upper is not None:
            format += '%^'
            arguments += [node.upper]
        format += ']%)%/'
        self.process(format, *arguments)

    visitSub = binary_operator

    def visitSubscript(self, node):
        indices = node.subs
        # FIXME: The 1-tuple case is not simplified, to be consistent with a
        # `compiler' bug which does not distinguishes between d[0] and d[0,].
        if (len(indices) == 1 and isinstance(indices[0], compiler.ast.Tuple)
              and len(indices[0].nodes) > 1):
            indices = indices[0].nodes
        format = self.maybe_del(node) + '%(%^%!%([%\\'
        arguments = [node.priority, node.expr, None, TUPLE_PRIORITY]
        if len(indices) == 1:
            format += '%!%^'
            arguments += indices
        else:
            format += ', %|'.join(['%^'] * len(indices))
            for index in indices:
                arguments += [index]
        format += ']%)%)%/'
        self.process(format, *arguments)

    def visitTuple(self, node):
        if len(node.nodes) == 0:
            format = '()'
            arguments = []
        elif len(node.nodes) == 1:
            format = '%(%!%^,%)'
            arguments = [TUPLE_PRIORITY, node.nodes[0]]
        else:
            format = '%('
            arguments = [TUPLE_PRIORITY]
            separator = ''
            for expression in node.nodes:
                format += separator + '%^'
                arguments += [expression]
                separator = ', %|'
            format += '%)'
        self.process(format, *arguments)

    visitUnaryAdd = unary_operator
    visitUnarySub = unary_operator

    ## Structuration and miscellaneous.

    def visitAssAttr(self, node):
        format = self.maybe_del(node)
        attributes = [node.attrname]
        node = node.expr
        while isinstance(node, compiler.ast.Getattr):
            attributes.append(node.attrname)
            node = node.expr
        attributes.reverse()
        self.process(format + '%(%^' + '%|.%s'*len(attributes) + '%)',
                     node.priority, node, *attributes)

    def visitAssName(self, node):
        self.process(self.maybe_del(node) + '%s', node.name)

    visitAssList = visitList
    visitAssTuple = visitTuple

    def visitClass(self, node):
        format = 'class %s%;'
        arguments = [node.name]
        if node.bases:
            format += '('
            separator = ''
            for base in node.bases:
                format += separator + '%^'
                arguments += [base]
                separator = ', %|'
            format += ')'
        format += '%:'
        self.process(format, *arguments)
        assert node.doc is None, node.doc
        self.process_body(node, node.code)

    def visitEllipsis(self, node):
        self.process('...')

    def visitFunction(self, node):
        flags = node.flags
        usuals = node.argnames[:]
        if node.kwargs:
            assert flags & compiler.consts.CO_VARKEYWORDS, flags
            flags &= ~compiler.consts.CO_VARKEYWORDS
            dstar_args = usuals.pop()
        else:
            dstar_args = None
        if node.varargs:
            assert flags & compiler.consts.CO_VARARGS, flags
            flags &= ~compiler.consts.CO_VARARGS
            star_args = usuals.pop()
        else:
            star_args = None
        assert not flags, flags
        if node.defaults:
            keys = usuals[-len(node.defaults):]
            usuals = usuals[:-len(node.defaults)]
        format = 'def %s%;(%\\'
        arguments = [node.name, TUPLE_PRIORITY]
        separator = ''
        for usual in usuals:
            format += separator + '%s'
            arguments += [usual]
            separator = ', %|'
        if node.defaults:
            for key, value in zip(keys, node.defaults):
                format += separator + '%s=%^'
                arguments += [key, value]
                separator = ', %|'
        if star_args is not None:
            format += separator + '*%s'
            arguments += [star_args]
            separator = ', %|'
        if dstar_args is not None:
            format += separator + '**%s'
            arguments += [dstar_args]
        format += ')%:%/'
        self.process(format, *arguments)
        assert node.doc is None, node.doc
        self.process_body(node, node.code)

    def visitKeyword(self, node):
        self.process('%s=%^', node.name, node.expr)

    def visitListCompFor(self, node):
        self.process(' %|for %#%^ in %^' + '%^'*len(node.ifs),
                     STATEMENT_PRIORITY, node.assign, node.list, *node.ifs)

    def visitListCompIf(self, node):
        self.process(' %|if %^', node.test)

    def visitModule(self, node):
        if node.doc is None:
            self.process('%^', node.node)
        else:
            assert isinstance(node.node, compiler.ast.Stmt)
            assert len(node.node.nodes) == 0, node.node
            self.process_string(node.doc, triple=True)

    def visitSliceobj(self, node):
        format = ''
        arguments = []
        separator = '%|'
        for expression in node.nodes:
            format += separator
            if not is_none(expression):
                format += '%^'
                arguments += [expression]
            separator = '%|:'
        self.process(format, *arguments)

    def visitStmt(self, node):
        assert len(node.nodes) == 1, node
        self.process('%^' * len(node.nodes), *node.nodes)

    ## Specialized rewritings.

    def rewrite_without_apply(self, node):
        if 'apply' not in self.rewrite_without:
            return
        from compiler.ast import CallFunc, Name
        if (isinstance(node, CallFunc) and len(node.args) == 2
              and not (node.star_args or node.dstar_args)
              and isinstance(node.node, Name) and node.node.name == 'apply'):
            self.visit(CallFunc(node.args[0], (), star_args=node.args[1]))
            return True
        return False

    def rewrite_without_find(self, node):
        if 'find' not in self.rewrite_without:
            return
        from compiler.ast import CallFunc, Compare, Const, Getattr, UnarySub
        if (isinstance(node, Compare) and len(node.ops) == 1
              and isinstance(node.expr, CallFunc)
              and len(node.expr.args) == 1
              and not (node.expr.star_args or node.expr.dstar_args)
              and isinstance(node.expr.node, Getattr)
              and node.expr.node.attrname == 'find'):
            operator, comparand = node.ops[0]
            if (isinstance(comparand, UnarySub)
                  and isinstance(comparand.expr, Const)
                  and comparand.expr.value == 1):
                if operator == '==':
                    operator = 'not in'
                elif operator == '!=':
                    operator = 'in'
                else:
                    return False
            elif isinstance(comparand, Const) and comparand.value == 0:
                if operator == '<':
                    operator = 'not in'
                elif operator == '>=':
                    operator = 'in'
                else:
                    return False
            self.visit(Compare(node.expr.args[0],
                               [(operator, node.expr.node.expr)]))
            return True
        return False

    def rewrite_without_has_key(self, node):
        if 'has_key' not in self.rewrite_without:
            return
        from compiler.ast import CallFunc, Compare, Getattr, Name
        if (isinstance(node, CallFunc) and len(node.args) == 1
              and not (node.star_args or node.dstar_args)
              and isinstance(node.node, Getattr)
              and node.node.attrname == 'has_key'):
            self.visit(Compare(node.args[0], [('in', node.node.expr)]))
            return True
        return False

    def rewrite_without_print(self, node, nl):
        if 'print' not in self.rewrite_without:
            return
        from compiler.ast import Add, CallFunc, Const, Getattr, Mod, Name, Tuple
        format = ''
        arguments = []
        separator = ''
        for expression in node.nodes:
            if (isinstance(expression, Mod)
                  and isinstance(expression.left, Const)
                  and isinstance(expression.left.value, str)):
                format += separator + expression.left.value
                if isinstance(expression.right, Tuple):
                    arguments += expression.right.nodes
                else:
                    arguments += [expression.right]
            elif (isinstance(expression, Const)
                  and isinstance(expression.value, str)
                  and '%' not in expression.value):
                format += separator + expression.value
            else:
                format += separator + '%s'
                arguments += [expression]
            separator = ' '
        if nl:
            separator = '\n'
        if node.dest is None:
            dest = Getattr(Name('sys'), 'stdout')
        else:
            dest = node.dest
        if len(arguments) == 0:
            self.visit(CallFunc(Getattr(dest, 'write'),
                                [Const(format + separator)]))
        elif len(arguments) == 1:
            if format == '%s':
                if (isinstance(arguments[0], Const)
                      and isinstance(arguments[0].value, str)):
                    self.visit(
                        CallFunc(Getattr(dest, 'write'),
                                 [Const(arguments[0].value + separator)]))
                else:
                    self.visit(
                        CallFunc(Getattr(dest, 'write'),
                                 [Add([CallFunc(Name('str'), arguments),
                                       Const(separator)])]))
            else:
                self.visit(CallFunc(Getattr(dest, 'write'),
                                    [Mod([Const(format + separator),
                                          arguments[0]])]))
        else:
            self.visit(CallFunc(Getattr(dest, 'write'),
                                [Mod([Const(format + separator),
                                      Tuple(arguments)])]))
        return True

    def rewrite_without_string(self, node):
        if 'string' not in self.rewrite_without:
            return
        from compiler.ast import CallFunc, Const, Getattr, Name
        if (isinstance(node, CallFunc) and len(node.args) > 0
              and not (node.star_args or node.dstar_args)
              and isinstance(node.node, Getattr)
              and isinstance(node.node.expr, Name)
              and node.node.expr.name == 'string'):
            method = node.node.attrname
            if method == 'join':
                if len(node.args) == 1:
                    self.visit(CallFunc(Getattr(Const(' '), 'join'),
                                        [node.args[0]]))
                    return True
                if len(node.args) == 2:
                    self.visit(CallFunc(Getattr(node.args[1], 'join'),
                                        [node.args[0]]))
                    return True
            elif method in ('capitalize', 'center', 'count', 'expandtabs',
                             'find', 'index', 'ljust', 'lower', 'lstrip',
                             'replace', 'rfind', 'rindex', 'rjust', 'rstrip',
                             'split', 'strip', 'swapcase', 'translate',
                             'upper', 'zfill'):
                self.visit(CallFunc(Getattr(node.args[0], method),
                                    node.args[1:]))
                return True
        return False

    ## Service methods.

    def maybe_del(self, node):
        if self.del_statement:
            assert node.flags == compiler.consts.OP_DELETE, (
                node, node.flags)
            return ''
        if node.flags == compiler.consts.OP_DELETE:
            self.del_statement = True
            return 'del '
        assert node.flags in (compiler.consts.OP_APPLY,
                               compiler.consts.OP_ASSIGN), (node, node.flags)
        return ''

    def process_body(self, node, statement):
        assert isinstance(statement, compiler.ast.Stmt), statement
        assert len(statement.nodes) == 1, statement
        if not hasattr(node, 'patch'):
            self.process(r'%\ %|%^%/', STATEMENT_PRIORITY, statement.nodes[0])

    def process_print(self, node, nl):
        if self.rewrite_without_print(node, nl):
            return
        format = 'print%#'
        arguments = [TUPLE_PRIORITY]
        separator = ' '
        if node.dest is not None:
            format += separator + '>>%^'
            arguments += [node.dest]
            separator = ', '
        for expression in node.nodes:
            format += separator + '%^'
            arguments += [expression]
            separator = ', '
        if not nl:
            format += ','
        self.process(format, *arguments)

    # FIXME: Maybe convey the original type? (raw, '', "", """)
    def process_string(self, text, triple=False):
        # Best format TEXT.  If TRIPLE, force a triple delimiter.

        # BEST is the length of the biggest sequence of letters.
        # SEQUENCE is the length of the most recent sequence of letters.
        # COUNTER is the number of letters within whole TEXT.
        best = 0
        sequence = 0
        counter = 0
        for character in text:
            if character.isalpha():
                counter += 1
                sequence += 1
            else:
                if sequence > best:
                    best = sequence
                sequence = 0

        # DELIMITER gets the best delimiter representing TEXT, that is,
        # a double quote if the the string seems to be using a natural
        # language, a single quote otherwise.  How to decide if a string
        # is a natural language fragment?  I have no choice than to rely on
        # simple heuristics.
        # FIXME: Any string within _() should always use double quotes.

        # Here is what Richard Stallman suggested me for `po-mode.el'.
        # If any three consecutive letters?  Then yes.  If never two
        # consecutive letters?  Then no.  Otherwise, yes if more letters
        # than non-letters.  However, this does not really satisfies me,
        # so I leave the code commented here.
        if False:
            if best >= 3 or best == 2 and 2 * counter > len(text):
                delimiter = '"'
            else:
                delimiter = '\''
        # I prefer trying the following heuristic, which considers that a
        # fragment is natural language if it has a space, if there is a word
        # of at least four letters, and if there is twice as much letters
        # than non-letters.
        if ' ' in text and best >= 4 and 3 * counter > len(text):
            delimiter = '"'
        else:
            delimiter = '\''
        # RAW flags that the string should be prefixed with `r'.
        raw = raw_best(text, delimiter)

        def try_line_delimiter():
            # Try, as a a layout, all whole on a line.
            self.write(python_string(text, delimiter))

        def try_simple_delimiter():
            # Try, as a layout, simple delimiters, would it meant splitting the
            # string on many pieces to be concatenated, each piece on its line.
            if raw:
                format_start = 'r' + delimiter
            else:
                format_start = delimiter
                substitutions = {delimiter: '\\' + delimiter, '\\': r'\\',
                                 '\a': r'\a', '\b': r'\b', '\f': r'\f',
                                 '\n': r'\n', '\t': r'\t', '\v': r'\v'}
            format_end = '%s' + delimiter
            format = '%(' + format_start
            arguments = [None]
            # Try a dummy edition, merely to know in which column the string
            # would start.  We'll foresee the splitting points once this
            # column is known.
            checkpoint = Checkpoint(self)
            self.process(format, *arguments)
            margin = column = self.column
            checkpoint.recall()
            del checkpoint.editor
            # Format a word at a time, including prefix spaces.  Change line
            # if there is no space left for the word.
            strategy = self.strategies[-1]
            fill = self.fill
            # Let's invent a dummy empty fragment at start, to inhibit a
            # second production of a format start.
            line_fragments = ['']
            word_fragments = ['']
            write = word_fragments.append
            WHITE, BLACK = range(2)
            state = WHITE
            for character in text:
                if character == ' ':
                    if state == BLACK:
                        if word_fragments:
                            word = ''.join(word_fragments)
                            del word_fragments[:]
                            # Ensure two slack columns, one for the delimiter
                            # if the string shall be broken on many lines,
                            # and another for the closing parenthesis ending
                            # a flurry of concatenated strings.
                            if (fill is not None
                                  and column + len(word) > Editor.limit - 2):
                                if strategy == LINE:
                                    raise Dead_End(_("String too long"))
                                format += format_end
                                arguments += [''.join(line_fragments)]
                                del line_fragments[:]
                                column = margin
                            if not line_fragments:
                                format += '%|' + format_start
                            line_fragments.append(word)
                            column += len(word)
                        state = WHITE
                    write(' ')
                else:
                    state = BLACK
                    if raw:
                        write(character)
                    elif character in substitutions:
                        write(substitutions[character])
                    elif not is_printable(character):
                        write(repr(character)[1:-1])
                    else:
                        write(character)
                    if character == '\n':
                        word = ''.join(word_fragments)
                        del word_fragments[:]
                        # For the `-2', see the comment above.
                        if (fill is not None
                              and column + len(word) > Editor.limit - 2):
                            if strategy == LINE:
                                raise Dead_End(_("String too long"))
                            format += format_end
                            arguments += [''.join(line_fragments)]
                            del line_fragments[:]
                        if not line_fragments:
                            format += '%|' + format_start
                        line_fragments.append(word)
                        format += format_end
                        arguments += [''.join(line_fragments)]
                        del line_fragments[:]
                        column = margin
                        state = WHITE
            if word_fragments:
                word = ''.join(word_fragments)
                # For the `-2', see the comment above.
                if (fill is not None
                      and column + len(word) > Editor.limit - 2):
                    if strategy == LINE:
                        raise Dead_End(_("String too long"))
                    format += format_end
                    arguments += [''.join(line_fragments)]
                    del line_fragments[:]
                if not line_fragments:
                    format += '%|' + format_start
                line_fragments.append(word)
            if line_fragments:
                format += format_end
                arguments += [''.join(line_fragments)]
            format += '%)'
            if fill is not None:
                self.fill = False
            try:
                self.process(format, *arguments)
            finally:
                self.fill = fill

        def try_triple_delimiter():
            # Try, for a layout, a triple delimiter.
            fragments = []
            write = fragments.append
            if raw:
                write('r' + delimiter*3 + '\\\n')
            else:
                write(delimiter*3 + '\\\n')
                # `\n' merely substitutes itself.
                substitutions = {'\n': '\n', '\\': r'\\', '\a': r'\a',
                                 '\b': r'\b', '\f': r'\f', '\v': r'\v'}
            if text:
                for character in text:
                    if raw:
                        write(character)
                    elif character in substitutions:
                        write(substitutions[character])
                    elif not is_printable(character):
                        write(repr(character)[1:-1])
                    else:
                        write(character)
            else:
                character = None
            if character != '\n':
                write('\\\n')
            write(delimiter * 3)
            self.write(''.join(fragments))

        if triple:
            try_triple_delimiter()
        elif self.strategies[-1] == LINE or len(text) < 25:
            try_line_delimiter()
        else:
            self.depth_level += 1
            try:
                def function((routine, strategy)):
                    self.strategies.append(strategy)
                    routine()
                    del self.strategies[-1]
                branching = (
                    Branching(self, None, None, function,
                                ((try_line_delimiter, LINE),
                                 (try_simple_delimiter, COLUMN),
                                 (try_triple_delimiter, COLUMN))))
                for position, index, function, outcome in branching:
                    try:
                        function(outcome)
                    except Dead_End:
                        pass
                    else:
                        branching.save_solution()
                branching.complete()
            finally:
                self.depth_level -= 1

    def process_constant(self, value):
        # Format the VALUE constant, which may not be a string.
        if isinstance(value, float):
            sys.stderr.write(
                _("WARNING: floating values are not dependable.\n"
                  "(There is a bug in `import compiler'.  Sigh!)"))
        self.write(repr(value))

    def process(self, format, *arguments):
        # Produce output FORMAT while interpreting %-CHARACTER sequences.
        # Some specifications consume one of the given ARGUMENTS, and all
        # ARGUMENTS should eventually be consumed by the FORMAT.

        # A `%%' sequence produces a single `%'.  `%_' produces a space or
        # not, according to the current priority or the value of SPACINGS.
        # SPACINGS tells a number of expression levels for which a space
        # is added on either side of each operator.  If zero or negative,
        # such spaces are not added.  `%s' and `%^' respectively edit a
        # string or a subtree, taken from arguments.

        # `%(' and `%)' surround a text fragment for which the priority may
        # differ, the new priority is given as an argument for `%(', a None
        # argument value tells that the priority should not change.  The text
        # fragment is parenthesized if its priority is not greater than the
        # priority of the surrounding text, or else, to better underline
        # the splitting in COLUMN or RETRACT strategies: in this last case,
        # the parentheses introduce continuation lines.  Whenever a `%('
        # and `%)' pair effectively generates parentheses, the effect of `%('
        # automatically implies `%\' with a -1 argument for the new priority,
        # and the effect of '%)' automatically implies `%/'.

        # '%\' adds indentation to the margin for continuation lines, and
        # forces a new priority received as argument, yet without producing
        # parentheses: this is useful after an explicit opening delimiter.
        # '%/' restores the previous margin and might attempt combining
        # accumulated lines for better filling lines.  `%|' ends the current
        # line and forces another to begin.  These three specifications have
        # no effect for LINE strategy.

        # '%;' forces, via MARGINS2 which might fix a minimum margin, a new
        # nesting of at least one and a half indentation for continuation
        # lines.  `%:' produces a colon and cancels the effect of a preceding
        # '%;'.  `%!', via ECONOMY, triggers the sparing of that parentheses
        # pair which would be needed for splitting purpose by the following
        # `%('; its effect is defused at the next writing.  `%#' forces the
        # priority given in an argument.

        # In the successive calls to EDIT for a given syntaxic tree, each
        # `%(' should eventually be matched by some `%)', each `%\' by `%/',
        # and each `%;' by `%:'.

        self.depth_level += 1
        try:
            # BRANCHINGS is a stack of branchings.  Each branching is created
            # with `%(' and destroyed with '%)'.  Strategy changes only
            # occur when the branching changes.
            branchings = []
            # Loop until FORMAT is completly processed, or a dead end could
            # not be recovered anymore.
            position = 0
            index = 0
            self.debug_format(format, arguments, position, index)
            while True:
                if position:
                    self.debug_format(format, arguments, position, index)
                try:
                    # Find next format specification and process the format
                    # fragment yielding to it.
                    previous = position
                    position = format.find('%', previous)
                    if position < 0:
                        if previous < len(format):
                            self.write(format[previous:])
                        break
                    if position > previous:
                        self.write(format[previous:position])
                    # Dispatch according to specification.
                    specification = format[position+1]
                    position += 2
                    strategy = self.strategies[-1]
                    if specification == '%':
                        self.write('%')
                    elif specification == '_':
                        if (self.priorities[-1] <= SPACING_PRIORITY
                              or self.spacings[-1] > 0):
                            self.write(' ')
                    elif specification == 's':
                        argument = arguments[index]
                        index += 1
                        if argument:
                            self.write(argument)
                    elif specification == '^':
                        argument = arguments[index]
                        index += 1
                        # Look ahead in FORMAT to decide for more slack.
                        slack = 0
                        look_ahead = position
                        while look_ahead < len(format):
                            if format[look_ahead] == '%':
                                look_ahead += 1
                                if format[look_ahead] in '%_():':
                                    slack += 1
                                elif format[look_ahead] in '|':
                                    if strategy != LINE:
                                        if format[look_ahead-2] == ' ':
                                            slack -= 1
                                        break
                            else:
                                slack += 1
                            look_ahead += 1
                        self.slacks.append(
                            self.slacks[-1] + slack)
                        # Format recursivley.
                        self.visit(argument)
                        del self.slacks[-1]
                    elif specification == '(':
                        argument = arguments[index]
                        index += 1
                        # Branching saves the current EDITOR state, including
                        # next POSITION in format and next argument INDEX.
                        if len(self.strategies) == 1:
                            maximum = RETRACT
                        else:
                            maximum = self.strategies[-1]
                        outcomes = [LINE]
                        if Editor.strategy != LINE:
                            outcomes.append(COLUMN)
                        if (Editor.strategy == RETRACT
                              and maximum == RETRACT):
                            outcomes.append(RETRACT)
                        def function(strategy):
                            self.strategies.append(strategy)
                            self.nest_parentheses(
                                branching, arguments[index - 1])
                        branching = Branching(self, position, index,
                                                  function, outcomes)
                        branchings.append(branching)
                        position, index, function, outcome = branching.next()
                        function(outcome)
                    elif specification == ')':
                        branching = branchings[-1]
                        self.unnest_parentheses(branching)
                        del self.strategies[-1]
                        branching.save_solution()
                        try:
                            position, index, function, outcome = (
                                branching.next())
                        except StopIteration:
                            branching.complete()
                            del branchings[-1]
                        else:
                            function(outcome)
                    elif specification == '\\':
                        argument = arguments[index]
                        index += 1
                        self.nest_margin()
                        self.priorities.append(argument)
                        # Note: SPACINGS is reset when # `%\' is explicitly
                        # used (like after `[' or `{'), but not when the effect
                        # of `%\' is implicit via `%('.  All the contrary,
                        # SPACINGS is forced to 2 in a similar context within
                        # a tuple.
                        if argument == TUPLE_PRIORITY:
                            self.spacings.append(2)
                        else:
                            self.spacings.append(0)
                    elif specification == '/':
                        self.unnest_margin()
                        del self.priorities[-1]
                        del self.spacings[-1]
                    elif specification == '|':
                        if strategy != LINE:
                            self.complete_line()
                    elif specification == ';':
                        self.margins2.append(self.margins[-1]
                                            + self.indentation
                                            + (self.indentation + 1)//2)
                    elif specification == ':':
                        self.write(':')
                        del self.margins2[-1]
                        self.margins.append(self.margins[-1]
                                           + self.indentation)
                    elif specification == '!':
                        self.economy = True
                    elif specification == '#':
                        argument = arguments[index]
                        index += 1
                        self.priorities[-1] = argument
                        if argument == TUPLE_PRIORITY:
                            self.spacings[-1] = 2
                    else:
                        assert False, specification
                except Dead_End, diagnostic:
                    while True:
                        if not branchings:
                            raise Dead_End(_("This is too difficult for me..."))
                        branching = branchings[-1]
                        try:
                            position, index, function, outcome = (
                                branching.next())
                        except StopIteration:
                            del branchings[-1]
                        else:
                            function(outcome)
                            break
            assert index == len(arguments), (index, arguments)
        finally:
            self.depth_level -= 1

    def nest_parentheses(self, branching, priority):
        if (priority is not None
              and not priority == self.priorities[-1] == CALL_PRIORITY
              and priority <= self.priorities[-1]):
            parenthesize = True
        elif self.strategies[-1] == LINE:
            parenthesize = False
        elif self.economy:
            parenthesize = False
            self.economy = False
        else:
            parenthesize = True
        if parenthesize:
            self.write('(')
            self.nesting += 1
            branching.closing = ')'
            self.spacings.append(2)
            self.nest_margin()
        else:
            branching.closing = None
            self.spacings.append(self.spacings[-1])
        if priority is None:
            self.priorities.append(self.priorities[-1])
        else:
            self.priorities.append(priority)

    def unnest_parentheses(self, branching):
        if branching.closing is not None:
            self.write(branching.closing)
            self.nesting -= 1
            self.unnest_margin()
        del self.priorities[-1]
        del self.spacings[-1]

    def nest_margin(self):
        if self.strategies[-1] is RETRACT:
            self.margins.append(self.margins[-1] + self.indentation)
            if self.column > self.margins[-1]:
                self.starts.append(len(self.blocks))
                self.complete_line()
            else:
                self.starts.append(len(self.blocks) - 1)
        else:
            self.margins.append(max(self.column, self.margins[-1]))
            self.starts.append(len(self.blocks) - 1)

    def unnest_margin(self):
        # Combine all line blocks into one, from START.
        start = self.starts.pop()
        if self.fill:
            index = start
            while index + 1 < len(self.blocks):
                if (self.blocks[index].find('\n', 0, -1) < 0
                      and self.blocks[index + 1].find('\n', 0, -1) < 0
                      and ((len(self.blocks[index])
                            + len(self.blocks[index + 1].lstrip()) - 1)
                           <= Editor.limit)):
                    self.blocks[index] = (
                        self.blocks[index][:-1]
                        + self.blocks.pop(index + 1).lstrip())
                    self.line -= 1
                    continue
                index += 1
        text = ''.join(self.blocks[start:])
        self.blocks[start:] = [text]
        self.column = len(text)
        position = text.rfind('\n')
        if position >= 0:
            self.column -= position + 1
        # Get back to previous margin.
        del self.margins[-1]

    def complete_line(self):
        if not self.nesting:
            raise Dead_End(_("Newline is not nested"))
        self.write('\n')
        if self.margins2[-1] is not None:
            self.margins[-1] = max(self.margins[-1], self.margins2[-1])

    def write(self, text):
        if self.column == 0:
            self.blocks.append('')
            self.line += 1
            text = ' '*self.margins[-1] + text
        self.blocks[-1] += text
        self.column += len(text)
        position = text.rfind('\n')
        if position >= 0:
            self.line += text.count('\n')
            self.column = len(text) - (position + 1)
            if self.column == 0:
                self.line -= 1
        if self.text_overflows():
            raise Dead_End(_("Line overflow"))
        self.economy = False

    def text_overflows(self):
        if (self.fill is not None
              and self.column + self.slacks[-1] > Editor.limit):
            self.debug_text(_("Overflow"))
            return True
        return False

class Branching:
    generation = 0

    def __init__(self, editor, position, index, function, outcomes):
        self.checkpoint = Checkpoint(editor)
        self.position = position
        self.index = index
        self.function = function
        self.outcomes = outcomes
        # Prepare for iteration.
        Branching.generation += 1
        self.generation = Branching.generation
        self.solutions = []
        self.next = iter(self).next

    def __del__(self):
        # Break circular references.
        for solution in self.solutions:
            del solution.editor
        if self.checkpoint is not None:
            del self.checkpoint.editor

    def __iter__(self):
        # Produce an iterator yielding the branching proper ARGUMENT and one
        # of possible OUTCOMES.  ARGUMENT may contain enough information for
        # resuming edition like at the start of branching.  It's a kind of
        # stunt around the fact that Python does not have continuations.
        if not self.outcomes:
            raise Dead_End(_("This is too difficult for me..."))
        editor = self.checkpoint.editor
        for counter, outcome in enumerate(self.outcomes):
            if counter > 0:
                self.checkpoint.recall()
            editor.debug('@%d %d/%d' % (Branching.generation,
                                         counter + 1,
                                         len(self.outcomes)))
            yield self.position, self.index, self.function, outcome

    def save_solution(self):
        editor = self.checkpoint.editor
        self.solutions.append(Checkpoint(editor))
        editor.debug(_("Save-%d") % len(self.solutions))

    def complete(self):
        if not self.solutions:
            raise Dead_End(_("This is too difficult for me..."))
        solution = min(self.solutions)
        if len(self.solutions) > 1:
            for counter, checkpoint in enumerate(self.solutions):
                checkpoint.debug_text(
                    '%s %d/%d' % (('  ', '->')[checkpoint is solution],
                                  counter + 1, len(self.solutions)),
                    checkpoint.line, checkpoint.visual_weight())
        solution.recall()

class Checkpoint(Editor):
    # A backtrack point may save, or restore, lists and integers which are
    # editor attributes.  It protects itself against later list modifications
    # within the editor.

    def __init__(self, editor):
        self.editor = editor
        for name, value in editor.__dict__.iteritems():
            if isinstance(value, list):
                setattr(self, name, value[:])
            elif isinstance(value, int):
                setattr(self, name, value)

    def recall(self):
        editor = self.editor
        for name, value in self.__dict__.iteritems():
            if name == 'editor':
                continue
            if isinstance(value, list):
                getattr(editor, name)[:] = value
            elif isinstance(value, int):
                setattr(editor, name, value)

    def __cmp__(self, other):
        return (cmp(self.line, other.line)
                or cmp(self.visual_weight(), other.visual_weight())
                or cmp(self.strategies, other.strategies))

    def visual_weight(self):
        # The visual weight of a set of lines is higher when lines have
        # unequal widths for their black mass.  The sum of the square of
        # widths is minimized when lines are equilibrated.  However, to
        # favor columnar alignments, this sum only counts continuation lines,
        # and the first line contributes only linearly to the visual weight.
        lines = ''.join(self.blocks).splitlines()
        weight = len(lines[0].strip()) * 12
        for line in lines[1:]:
            width = len(line.strip())
            weight += width * width
        return weight

## Stylistic nits.

if vim is not None:
    vim.command('highlight Nit term=reverse cterm=bold ctermbg=1'
                ' gui=bold guibg=Cyan')

def correct_nit(mode):
    # Correct the nit right under the cursor if any, then move to the next nit.
    for nit in MetaNit.register:
        if nit.confirm_error(*current_cursor()):
            nit.correct()
            nit.reposition()
            return
    find_nit(mode)

def find_nit(mode):
    # Find next stylistic nit.
    # FIXME: `\\' repeated on a sequence of empty lines do not advance cursor.
    buffer = vim.current.buffer
    row, column = current_cursor()
    line = buffer[row]
    # If nothing changed since last time, advance cursor.  Otherwise,
    # restart analysis of the current line from its beginning.
    if (row == Nit.previous_row
          and column == Nit.previous_column
          and line[column:].startswith(Nit.previous_fragment)):
        column += 1
        if column == len(line):
            row += 1
            column = 0
            if row + 1 <= len(buffer):
                line = buffer[row]
    else:
        column = 0
    # Search a nit from the cursor position.
    while row < len(buffer):
        # Keep the match being most on the left, and then, the longest one.
        start = None
        for nit in MetaNit.register:
            pair = nit.find_error(row, column)
            if (pair is not None
                    and (start is None
                         or pair[0] < start
                         or pair[0] == start and pair[1] > end)):
                start, end = pair
                moaning = nit.moaning
        if start is not None:
            # Highlight nit and reposition cursor.
            change_current_cursor(row, start)
            fragment = line[start:end]
            if fragment:
                argument = (fragment.replace('\\', '\\\\')
                            .replace('/', '\\/').replace('[', '\\[')
                            .replace('*', '\\*'))
                vim.command('match Nit /%s/' % argument)
            else:
                vim.command('match')
            sys.stderr.write(moaning)
            Nit.previous_row = row
            Nit.previous_column = start
            Nit.previous_fragment = fragment
            return
        # Go to the beginning of next line.
        row += 1
        column = 0
        if row < len(buffer):
            line = buffer[row]
    sys.stderr.write(_("The reminder of the file looks good...\n"))

class MetaNit(type):
    # Keep a registry of one instance per stylistic nit class.  Pre-compile the
    # class pattern if any.
    register = []

    def __init__(self, name, bases, dict):
        type.__init__(self, name, bases, dict)
        if name != 'Nit':
            MetaNit.register.append(self())
        if hasattr(self, 'pattern'):
            import re
            self.pattern = re.compile(self.pattern)

class Nit:
    __metaclass__ = MetaNit
    # MOANING holds a short explanation for the user.
    moaning = "Syntactic nit."
    # When SYNTEXT is None, the given pattern may match character strings
    # or comments.  Otherwise, SYNTEXT is a number, often 0, a position
    # from the start of the matched text (or its end if negative).  Then,
    # the character at this position should not be part of a character string
    # nor a comment.
    syntext = None
    # After a trustable automatic correction, that is, one which does not
    # change Python semantic, REPOSITIONING may be set True in the nit, as an
    # indication that the cursor should be moved on the next nit.  Otherwise,
    # without an automatic correction, human intervention is required.
    repositioning = False
    # The three next variables are `global' to all nits.  They are used to
    # detect if anything changed since last found nit, and consequently,
    # whether if the user decided to ignore it.  In such case, we have to
    # unconditionally move to the next nit.  If a correction occurred,
    # the line should be studied from its start, in case the correction
    # introduced another nit.
    previous_row = None
    previous_column = None
    previous_fragment = ''

    def find_error(self, row, column):
        buffer = vim.current.buffer
        line = buffer[row]
        if hasattr(self, 'pattern'):
            match = self.pattern.search(line, column)
            while match:
                if self.confirm_error(row, match.start()):
                    return match.start(), match.end()
                match = self.pattern.search(line, match.start() + 1)
        else:
            while True:
                if self.confirm_error(row, column):
                    return column, len(line)
                if column == len(line):
                    break
                column += 1

    def confirm_error(self, row, column):
        assert hasattr(self, 'pattern'), self
        buffer = vim.current.buffer
        match = self.pattern.match(buffer[row], column)
        if match is None:
            return
        syntext = self.syntext
        if syntext is None:
            self.match = match
            return match
        if syntext < 0:
            syntext += match.end() - match.start()
        if (vim.eval('synIDattr(synID(%d, %d, 0), "name")'
                     % (row + 1, column + 1 + syntext))
              in ('pythonComment', 'pythonRawString', 'pythonString')):
            return
        self.match = match
        return match

    def correct(self):
        # By default, the program selects and edit a correction.
        sys.stderr.write(_("Here, I need a human to help!\n"))
        self.cancel_previous()

    def reposition(self):
        if self.repositioning:
            find_nit('n')

    def replace_text(self, new):
        assert hasattr(self, 'pattern'), self
        buffer = vim.current.buffer
        row = current_cursor()[0]
        line = buffer[row]
        buffer[row] = (line[:self.match.start()]
                          + self.match.expand(new)
                          + line[self.match.end():])
        self.cancel_previous()

    def cancel_previous(self):
        Nit.previous_row = None
        Nit.previous_column = None
        Nit.previous_fragment = ''

class Empty_File(Nit):
    # An empty module may not be empty.
    moaning = "Empty module."

    def find_error(self, row, column):
        if self.confirm_error(row, column):
            return 0, 0

    def confirm_error(self, row, column):
        buffer = vim.current.buffer
        return len(buffer) == 0 or len(buffer) == 1 and not buffer[0]

    def correct(self):
        # Insert the skeleton of a Python program.
        vim.current.buffer[:] = [
            '#!/usr/bin/env python',
            '# -*- coding: utf-8 -*-',
            '',
            '"""\\',
            '',
            '"""',
            '',
            '__metaclass__ = type',
            'import sys',
            '',
            'class Main:',
            '',
            '    def main(self, *arguments):',
            '        import getopt',
            '        options, arguments = getopt.getopt(arguments, \'\')',
            '        for option, value in options:',
            '            pass',
            '',
            'run = Main()',
            'main = run.main',
            '',
            'if __name__ == \'__main__\':',
            '    main(*sys.argv[1:])',
            ]
        self.cancel_previous()

    def reposition(self):
        # Trigger insertion within the doc-string.
        change_current_cursor(4, 0)
        vim.command('startinsert')

class Double_Emptyline(Nit):
    # No use for many sucessive empty lines.
    moaning = _("Multiple blank lines in a row.")

    def find_error(self, row, column):
        if self.confirm_error(row, column):
            return 0, 0

    def confirm_error(self, row, column):
        buffer = vim.current.buffer
        if len(buffer[row]) == 0:
            return row + 1 < len(buffer) and len(buffer[row+1]) == 0

    def correct(self):
        # Get rid of extraneous lines.
        retract_fill_layout(current_cursor()[0])
        self.repositioning = True

class Tab(Nit):
    # There should not be any horizontal tab in the file.
    moaning = _("TAB within source.")
    pattern = r'\t\t*'

    def correct(self):
        # Within the left margin, replace each HT by eight spaces.
        # Later in the line, prefer the writing `\t'.
        if self.match.start() == 0:
            self.replace_text(' ' * 8 * len(self.match.group()))
            self.repositioning = True
        else:
            self.replace_text(r'\t' * len(self.match.group()))

class Spaces(Nit):
    # Tokens should not be separated by more than one space.
    moaning = _("Multiple spaces in a row.")
    pattern = '([^ ])   *([^ #])'
    syntext = 1

    def correct(self):
        # Get rid of extraneous spaces.
        before, after = self.match.group(1, 2)
        if before in '([{' or after in ',;.:)]}':
            self.replace_text(before + after)
        else:
            self.replace_text(before + ' ' + after)
        self.repositioning = True

class Space_Newline(Nit):
    # A line may not have spurious trailing whitespace.
    moaning = _("Trailing spaces.")
    pattern = r'[ \t][ \t]*$'

    def correct(self):
        # Get rid of trailing whitespace.
        self.replace_text('')
        self.repositioning = True

class Backslash_Newline(Nit):
    # A backslash at end of line should be always avoided, save for when it
    # immediately follows a triple double quote.
    moaning = _("Escaped newline.")
    pattern = r' *\\$'

    def confirm_error(self, row, column):
        if Nit.confirm_error(self, row, column):
            buffer = vim.current.buffer
            line = buffer[row]
            return ((column == 0 or line[column-1] != ' ')
                    and not line.endswith('"""\\'))

    def correct(self):
        self.replace_text('')

class Par_Space(Nit):
    # An opening parenthesis should not be followed by a space.  Same for
    # an opening bracket or and opening brace.
    moaning = _("Space after opening bracket, brace or parenthesis.")
    pattern = r'([(\[{])  *'

    def correct(self):
        # Remove following spaces.
        self.replace_text(r'\1')
        self.repositioning = True

class Space_These(Nit):
    # A closing parenthesis should be be preceded by a space.  Same for a
    # closing bracket or a closing brace.
    moaning = _("Space before closing bracket, brace or parenthesis.")
    pattern = r'([^ ])  *([)\]}])'

    def correct(self):
        # Remove preceding spaces.
        self.replace_text(r'\1\2')
        self.repositioning = True

class Comma_Black(Nit):
    # A comma should be followed by a space.  Same for semi-colons.
    moaning = _("Punctuation not followed by space.")
    pattern = '([,;])([^ )])'
    syntext = 0

    def correct(self):
        # Add one space.
        self.replace_text(r'\1 \2')
        self.repositioning = True

class Space_Comma(Nit):
    # A comma may not be preceded by a space.  Same for colons and semi-colons.
    moaning = _("Punctuation preceded by space.")
    pattern = '(  *)([,:;])'

    def confirm_error(self, row, column):
        if Nit.confirm_error(self, row, column):
            buffer = vim.current.buffer
            return column == 0 or buffer[row][column-1] != ' '

    def correct(self):
        # Move comma back before spaces.
        self.replace_text(r'\2\1')
        self.repositioning = True

class Black_Equal(Nit):
    # `=' and `==' should be preceded by a space on average.  However,
    # for keyword parameters, there is no space on either side of `='.
    moaning = _("Assignment or comparison symbol not preceded by space.")
    pattern = '([^-+*/ <=>!&|])=  *'
    syntext = 0

    def correct(self):
        # Add missing space.
        self.replace_text(r'\1 = ')
        self.repositioning = True

class Equal_Black(Nit):
    # `=' and `==' should be followed by a space on average.  However,
    # for keyword parameters, there is no space on either side of `='.
    moaning = _("Assignment or comparison symbol not followed by space.")
    pattern = '  *=([^ =])'
    syntext = 0

    def confirm_error(self, row, column):
        if Nit.confirm_error(self, row, column):
            buffer = vim.current.buffer
            return column == 0 or buffer[row][column-1] != ' '

    def correct(self):
        # Add missing space.
        self.replace_text(r' = \1')
        self.repositioning = True

class Comment_Statement(Nit):
    # A comment should be alone on its line, it may not end a logical line
    # which already holds something else.
    moaning = _("In-line comment.")
    pattern = '[^ ] *#'
    syntext = -1

    def correct(self):
        # Tear off comment and put it alone on a separate line.  The comment
        # normally precedes the line, unless the Python line ends with
        # a colon, in which case the comment follows the line.  A capital
        # letter is forced at the beginning of comment, and a missing sentence
        # terminator gets added.
        buffer = vim.current.buffer
        row = current_cursor()[0]
        line = buffer[row]
        python_code = line[:self.match.start()+1]
        comment = line[self.match.end()+1:]
        if comment.startswith(' '):
            comment = comment[1:]
        if comment:
            if comment[0].islower():
                comment = comment[0].upper() + comment[1:]
            if comment[-1] not in '.!?':
                comment += '.'
            if python_code.endswith(':'):
                buffer[row:row+1] = [
                    python_code,
                    '%*s# %s' % (left_margin(buffer[row+1]), '',
                                 comment)]
            else:
                buffer[row:row+1] = [
                    '%*s# %s' % (left_margin(python_code), '', comment),
                    python_code]
        else:
            buffer[row] = python_code
        self.cancel_previous()

class Operator_Newline:
    # An operator may not end a line.
    moaning = _("Operator at end of line.")
    pattern = r'(\band|\bor|[-+*/%<=>!])$'
    syntext = 0

    def correct(self):
        # Move the operator at the beginning of the next line.
        buffer = vim.current.buffer
        row = current_cursor()[0]
        line = buffer[row]
        operator = self.match.group().lstrip()
        buffer[row] = line[:self.match.start()].rstrip()
        line = buffer[row+1]
        margin = left_margin(line)
        buffer[row+1] = '%s%s %s' % (line[:margin], operator, line[margin:])
        self.cancel_previous()

class Double_Quote_No_Word(Nit):
    # A single quote should be used rather than a double quote to delimit
    # a string holding only special characters or isolated letters.
    moaning = _("Double-quotes with no words (consider single-quotes).")
    pattern = r'"(\\.|[^"])*"'

    def confirm_error(self, row, column):
        if Nit.confirm_error(self, row, column):
            buffer = vim.current.buffer
            text = eval(self.match.group(), {}, {})
            if not text:
                return True
            if (vim.eval("synIDattr(synID(%d, %d, 0), \"name\")"
                         % (row + 1, column + 1))
                  not in ('pythonRawString', 'pythonString')):
                return False
            return not re.search('[A-Za-z][A-Za-z]', text)

    def correct(self):
        text = eval(self.match.group(), {}, {})
        self.replace_text(python_string(text, '\''))
        self.repositioning = True

class Triple_Double_Quotes(Nit):
    # A triple double quote at the beginning of a string should either
    # start a line or follow a comma or opening parenthesis, and be only
    # followed by a backslash.  If it ends a string, it should either be
    # alone, or be followed either by a comma or a closing parenthesis.
    moaning = _("Questionable formatting of triple quotes.")
    pattern = '"""'

    def confirm_error(self, row, column):
        if Nit.confirm_error(self, row, column):
            buffer = vim.current.buffer
            line = buffer[row]
            suffix = line[column+3:]
            if suffix == '\\':
                if column > 0 and line[column-1] == '(':
                    return False
                if column > 1 and line[column-2:column] == ', ':
                    return False
                if not line[:column].lstrip():
                    return False
                return True
            if suffix in ('', ',', ')'):
                return column > 0
            return True

class Lenghty_Line(Nit):
    # Lines should fit within Editor.LIMIT columns.
    moaning = _("Line exceeds %d characters.")

    def find_error(self, row, column):
        buffer = vim.current.buffer
        if column <= Editor.limit and len(buffer[row]) > Editor.limit:
            self.moaning = Lenghty_Line.moaning % Editor.limit
            return Editor.limit, len(buffer[row])

    def confirm_error(self, row, column):
        buffer = vim.current.buffer
        return (column == Editor.limit
                and len(buffer[row]) > Editor.limit)

    def correct(self):
        # Reformat the whole Python code.
        retract_fill_layout(current_cursor()[0])

class Apply(Nit):
    # `apply(FUNCTION, ARGUMENTS)' is better written `FUNCTION(*ARGUMENTS)'.
    moaning = (_("Use of `apply' function -- `function(*arguments)' is"
                 " preferred."))
    pattern = r'\bapply\('

    def correct(self):
        # Reformat the whole Python code.
        Editor.rewrite_without.append('apply')
        retract_fill_layout(current_cursor()[0])
        Editor.rewrite_without.pop()

class Close(Nit):
    # `OBJECT.close()' is seldomly required if OBJECT is a file.
    moaning = _("Use of `close' method (possibly unnecessary).")
    pattern = r'\.close\(\)'

class Eval(Nit):
    # `eval()' should be avoided as much as possible.
    moaning = _("Use of `eval' function (rethink the algorithm).")
    pattern = r'\beval\('

class Exec(Nit):
    # `exec' should be avoided as much as possible.
    moaning = _("Use of `exec' statement (rethink the algorithm).")
    pattern = r'\bexec\b'

class Execfile(Nit):
    # `execfile()' should be avoided as much as possible.
    moaning = _("Use of `execfile' function (rethink the algorithm).")
    pattern = r'\bexecfile\('

class Find(Nit):
    # `STRING.find(SUBSTRING)' is bettern written `SUBSTRING in STRING'.
    moaning = _("Use of `find' method (consider using `in' instead).")
    pattern = r'\.find\('

    def correct(self):
        # Reformat the whole Python code.
        Editor.rewrite_without.append('find')
        retract_fill_layout(current_cursor()[0])
        Editor.rewrite_without.pop()

class Global(Nit):
    # `global' should be avoided as much as possible.
    moaning = (_("Use of `global' statement (consider using class variables"
                 " instead)."))
    pattern = r'\bglobal\b'

class Has_Key(Nit):
    # `OBJECT.has_key(KEY)' is better written `KEY in OBJECT'.
    moaning = _("Use of `has_key' method (consider using `in' instead).")
    pattern = r'\.has_key\('

    def correct(self):
        # Reformat the whole Python code.
        Editor.rewrite_without.append('has_key')
        retract_fill_layout(current_cursor()[0])
        Editor.rewrite_without.pop()

class Input(Nit):
    # `input()' should be avoided as much as possible.
    moaning = _("Use of `input' function (rethink the algorithm).")
    pattern = r'\binput\('

class Import_Star(Nit):
    # L'énoncé `import *' should generally be avoided.
    moaning = _("Use of `import *' (be explicit about what to import instead).")
    pattern = r'\bimport \*'

class Items(Nit):
    # `OBJECT.items()' is often better written `OBJECT.iteritems()'.
    moaning = _("Use of `items' method (consider using `iteritems' instead).")
    pattern = r'\.items\(\)'

    def correct(self):
        # Use `iteritems'.
        self.replace_text('.iteritems()')

class Iterkeys(Nit):
    # `OBJECT.iterkeys()' is better written `OBJECT', used as an iterator.
    moaning = _("Use of `iterkeys' method (possibly unnecessary).")
    pattern = r'\.iterkeys\(\)'

    def correct(self):
        # Avoid calling `iterkeys'.
        self.replace_text('')

class Keys(Nit):
    # `OBJECT.keys()' is better written `OBJECT', used as an iterator.
    moaning = _("Use of `keys' method (possibly unnecessary).")
    pattern = r'\.keys\(\)'

    def correct(self):
        # Avoid calling `keys'.
        self.replace_text('')

class Open(Nit):
    # `open(FILENAME)' is better written `file(FILENAME)'.
    moaning = _("Use of `open' method (consider using `file' instead).")
    pattern = r'\bopen\('

    def correct(self):
        # Use `file'.
        self.replace_text('file(')

class Print(Nit):
    # The `print' statement should be reserved for debugging.
    moaning = _("Use of `print' statement (is it meant for debugging?).")
    pattern = r'\bprint\b'
    syntext = 0

    def correct(self):
        # Reformat the whole Python code.
        Editor.rewrite_without.append('print')
        retract_fill_layout(current_cursor()[0])
        Editor.rewrite_without.pop()

class Readlines(Nit):
    # `OBJECT.readlines()' is better written `OBJECT', used as an iterator.
    moaning = _("Use of `readlines' method (possibly unnecessary).")
    pattern = r'\.readlines\(\)'

    def correct(self):
        # Avoid calling `readlines'.
        self.replace_text('')

class String(Nit):
    # The `string' module is almost obsolete.
    moaning = (_("Use of `string' module (consider using string methods"
                 " instead)."))
    pattern = r'\bstring\.|\bimport.*\bstring\b'
    syntext = 0

    def correct(self):
        # Reformat the whole Python code.
        Editor.rewrite_without.append('string')
        retract_fill_layout(current_cursor()[0])
        Editor.rewrite_without.pop()

class Type(Nit):
    # `OBJECT is type(CONSTANT)' is rewritten `isinstance(OBJECT, TYPE)'.
    moaning = _("Use of `type' function (consider using `isinstance' instead).")
    pattern = r'(\bis |==) *type\('

class Values(Nit):
    # `OBJECT.values()' is often better written `OBJECT.itervalues()'.
    moaning = _("Use of `values' method (consider using `itervalues' instead).")
    pattern = r'\.values\(\)'

    def correct(self):
        # Use `itervalues'.
        self.replace_text('.itervalues()')

class Xreadlines(Nit):
    # `OBJECT.xreadlines()' is better written `OBJECT', used as an iterator.
    moaning = _("Use of `xreadlines' method (possibly unnecessary).")
    pattern = r'\.xreadlines\(\)'

    def correct(self):
        # Do not call `xreadlines'.
        self.replace_text('')

## A few other simple actions.

def choose_debug(mode):
    Editor.debugging = not Editor.debugging
    if Editor.debugging:
        sys.stdout.write(_("Tracing enabled, quite verbose."))
    else:
        sys.stdout.write(_("Tracing disabled."))

def choose_filling_tool(mode):
    def next_value(value, choice):
        return choice[(list(choice).index(value) + 1) % len(choice)]
    Layout_Engine.filling_tool = next_value(Layout_Engine.filling_tool,
                                            Layout_Engine.filling_tool_choices)
    sys.stdout.write(_("Comments will be filled using `%s'.")
                     % Layout_Engine.filling_tool)

def add_parentheses(mode):
    row, column = current_cursor()
    buffer = vim.current.buffer
    line = buffer[row]
    if line.endswith(':'):
        buffer[row] = line[:column] + '(' + line[column:-1] + '):'
    else:
        buffer[row] = line[:column] + '(' + line[column:] + ')'
    change_current_cursor(row, column + 1)

def remove_parentheses(mode):
    row1, column1 = current_cursor()
    vim.command('normal %')
    row2, column2 = current_cursor()
    vim.command('normal %')
    if (row1, column1) > (row2, column2):
        row1, row2 = row2, row1
        column1, column2 = column2, column1
    buffer = vim.current.buffer
    for row, column in (row2, column2), (row1, column1):
        line = buffer[row]
        buffer[row] = line[:column] + line[column+1:]
    change_current_cursor(row1, column1)

def force_single_quotes(mode):
    change_string('"', '\'')

def force_double_quotes(mode):
    change_string('\'', '"')

def change_string(before, after):
    # BEFORE and AFTER are one-character strings, the delimiter.
    row, column = current_cursor()
    buffer = vim.current.buffer
    line = buffer[row]
    match = (re.compile(r'r?%s(\\.|[^%s])*%s' % (before, before, before))
             .search)(line, column)
    if match:
        text = python_string(eval(match.group(), {}, {}), after)
        buffer[row] = line[:match.start()] + text + line[match.end():]
        change_current_cursor(row, match.start() + len(text))

## Service routines.

# Should we count rows and columns from 0 or 1?  Within the mode line
# under the window, Vim displays row and column both from 1.  Within
# `vim.current.window.cursor', row is counted from 1 and column from 0.
# Within `vim.current.buffer', rows are counted from 0, the Python way.
# In this program, both rows and columns are counted from 0.

def current_cursor():
    row, column = vim.current.window.cursor
    return row - 1, column

def change_current_cursor(row, column):
    vim.current.window.cursor = row + 1, column

def is_none(node):
    # Returns True if the node represents the None constant.
    return isinstance(node, compiler.ast.Const) and node.value is None

def python_string(text, delimiter):
    # Return TEXT representation as a Python string delimited with DELIMITER,
    # which is either a single quote or a double quote.  The raw attribute
    # is decided automatically.
    if raw_best(text, delimiter):
        return 'r' + delimiter + text + delimiter
    fragments = []
    write = fragments.append
    substitutions = {delimiter: '\\' + delimiter, '\\': r'\\', '\a': r'\a',
                     '\b': r'\b', '\f': r'\f', '\n': r'\n', '\t': r'\t',
                     '\v': r'\v'}
    write(delimiter)
    for character in text:
        if character in substitutions:
            write(substitutions[character])
        elif not is_printable(character):
            write(repr(character)[1:-1])
        else:
            write(character)
    write(delimiter)
    return ''.join(fragments)

def raw_best(text, delimiter):
    # Returns True if the string is better presented as "raw".
    if '\\' not in text:
        return False
    if (len(text) - len(text.rstrip('\\'))) % 2 != 0:
        return False
    for character in text:
        if character == delimiter or not is_printable(character):
            return False
    return True

try:
    import unicodedata
except ImportError:

    def is_printable(character):
        value = ord(character)
        # Returns True is the ISO 8859-1 character is printable.
        return not (0 <= value < 32 or 127 <= value < 160)
else:

    def is_printable(character):
        # Returns True if the character is printable according to Unicode.
        return unicodedata.category(unichr(ord(character))) != 'Cc'

def left_margin(text):
    # Returns the number of consecutive spaces prefixing the text.
    return len(text) - len(text.lstrip())

if vim is not None:
    install_vim()
    for command in ("""\
augroup Pynits
  autocmd!
  autocmd FileType python python pynits.install_vim()
  autocmd BufWrite * python pynits.adjust_coding()
augroup END
""").splitlines():
        vim.command(command.lstrip())

if __name__ == '__main__':
    run = Main()
    run.main(*sys.argv[1:])
