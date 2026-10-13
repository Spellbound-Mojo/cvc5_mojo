/* Native-only diagnostic: parser terms belong to the solver's term manager,
 * even when a different symbol manager exports them through its C wrapper.
 * Keep both managers alive throughout; do not exercise a dangling C handle.
 */
#include <cvc5/c/cvc5.h>
#include <cvc5/c/cvc5_parser.h>
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

static void check(void) { assert(!cvc5_has_error()); }

static void exercise(bool shared)
{
  Cvc5TermManager* first = cvc5_term_manager_new();
  Cvc5TermManager* second = cvc5_term_manager_new();
  Cvc5TermManager* symbol_tm = shared ? first : second;
  Cvc5* solver = cvc5_new(first);
  Cvc5SymbolManager* symbols = cvc5_symbol_manager_new(symbol_tm);
  Cvc5InputParser* parser = cvc5_parser_new(solver, symbols);
  check();
  cvc5_parser_set_str_input(parser, CVC5_INPUT_LANGUAGE_SMT_LIB_2_6,
                            "(set-logic QF_UF)(declare-const p Bool)", "managers");
  check();
  while (!cvc5_parser_done(parser))
  {
    const char* error = NULL;
    Cvc5Command command = cvc5_parser_next_command(parser, &error);
    check();
    assert(!error);
    if (!command) break;
    cvc5_cmd_invoke(command, solver, symbols);
    check();
    cvc5_cmd_release(command);
    check();
  }
  size_t count = 0;
  const Cvc5Term* terms = cvc5_sm_get_declared_terms(cvc5_parser_get_sm(parser), &count);
  check();
  assert(count == 1);
  Cvc5Term value = terms[0];
  Cvc5Term result = cvc5_mk_term(symbol_tm, CVC5_KIND_NOT, 1, &value);
  if (shared)
  {
    check();
    assert(result);
    cvc5_term_release(result);
  }
  else
  {
    assert(!result && cvc5_has_error());
    assert(strstr(cvc5_get_error_message(), "associated with this term manager"));
    cvc5_reset_error();
  }
  /* With the solver's original manager the same term is usable in both cases. */
  result = cvc5_mk_term(first, CVC5_KIND_NOT, 1, &value);
  check();
  assert(strcmp(cvc5_term_to_string(result), "(not p)") == 0);
  check();
  cvc5_term_release(result);
  cvc5_term_release(value);
  cvc5_parser_delete(parser);
  cvc5_symbol_manager_delete(symbols);
  cvc5_delete(solver);
  cvc5_term_manager_delete(first);
  cvc5_term_manager_delete(second);
  check();
}

int main(void)
{
  exercise(true);
  exercise(false);
  puts("native mixed-manager constraint reproduced");
}
