/* Independent fixed-input controls against the cached public C header. */
#define _POSIX_C_SOURCE 200809L
#include <cvc5/c/cvc5.h>
#include <cvc5/c/cvc5_parser.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "support.h"

static uint64_t now(void)
{
  struct timespec t;
  require(clock_gettime(CLOCK_MONOTONIC, &t) == 0, "clock_gettime failed");
  return (uint64_t)t.tv_sec * 1000000000 + (uint64_t)t.tv_nsec;
}
static void sample(const char *path, int phase, uint64_t count, uint64_t elapsed, uint64_t checksum)
{
  FILE *status = fopen("/proc/self/status", "r");
  require(status != NULL, "open status failed");
  char line[512];
  unsigned long rss = 0;
  while (fgets(line, sizeof(line), status))
    if (sscanf(line, "VmRSS: %lu kB", &rss) == 1) break;
  fclose(status);
  require(rss > 0, "VmRSS absent");
  FILE *out = fopen(path, "a");
  require(out != NULL, "open checkpoint failed");
  fprintf(out, "%d\t%" PRIu64 "\t%" PRIu64 "\t%lu\t%" PRIu64 "\n", phase, count, elapsed, rss, checksum);
  require(fclose(out) == 0, "close checkpoint failed");
}

typedef struct {
  Cvc5TermManager *tm;
  Cvc5 *solver;
  Cvc5Term start, truth, falsity;
  Cvc5Grammar reused;
  Cvc5InputParser *parser;
  Cvc5Sort datatype_sort;
  Cvc5SynthResult synthesis;
  const char *mode;
  int retain_extra;
} Control;

static Cvc5DatatypeDecl declaration(Cvc5TermManager *tm)
{
  Cvc5DatatypeDecl decl = V(cvc5_mk_dt_decl(tm, "Box", false));
  Cvc5DatatypeDecl copied = V(cvc5_dt_decl_copy(decl));
  Cvc5DatatypeConstructorDecl cons = V(cvc5_mk_dt_cons_decl(tm, "box"));
  Cvc5DatatypeConstructorDecl cons_copy = V(cvc5_dt_cons_decl_copy(cons));
  Cvc5Sort boolean = V(cvc5_get_boolean_sort(tm));
  DO(cvc5_dt_cons_decl_add_selector(cons_copy, "value", boolean));
  DO(cvc5_sort_release(boolean));
  DO(cvc5_dt_decl_add_constructor(copied, cons_copy));
  require(!strcmp(V(cvc5_dt_decl_get_name(decl)), "Box"), "declaration name mismatch");
  require(V(cvc5_dt_decl_get_num_constructors(copied)) == 1, "constructor count mismatch");
  DO(cvc5_dt_cons_decl_release(cons_copy));
  DO(cvc5_dt_cons_decl_release(cons));
  DO(cvc5_dt_decl_release(decl));
  return copied;
}

static uint64_t stat_checksum(Cvc5Stat stat)
{
  uint64_t sum = 16 * V(cvc5_stat_is_default(stat)) + 32 * V(cvc5_stat_is_internal(stat));
  if (V(cvc5_stat_is_int(stat))) { (void)V(cvc5_stat_get_int(stat)); return sum + 1; }
  if (V(cvc5_stat_is_double(stat))) { (void)V(cvc5_stat_get_double(stat)); return sum + 2; }
  if (V(cvc5_stat_is_string(stat)))
  {
    char *s = strdup(V(cvc5_stat_get_string(stat)));
    require(s != NULL, "allocation failed");
    free(s);
    return sum + 3;
  }
  require(V(cvc5_stat_is_histogram(stat)), "unknown statistic kind");
  const char **names = NULL;
  uint64_t *values = NULL;
  size_t size = 0;
  DO(cvc5_stat_get_histogram(stat, &names, &values, &size));
  sum += 4 + 64 * size;
  for (size_t i = 0; i < size; ++i)
  {
    char *key = strdup(names[i]);
    require(key != NULL && strlen(key) > 0, "empty histogram key");
    sum += strlen(key);
    free(key);
  }
  return sum;
}

static Control create(const char *mode, int retain_extra)
{
  Control c = {.mode = mode, .retain_extra = retain_extra};
  c.tm = V(cvc5_term_manager_new());
  c.solver = V(cvc5_new(c.tm));
  Cvc5Sort sort = V(cvc5_get_boolean_sort(c.tm));
  c.start = V(cvc5_mk_var(c.tm, sort, "Γ"));
  DO(cvc5_sort_release(sort));
  c.truth = V(cvc5_mk_true(c.tm));
  c.falsity = V(cvc5_mk_false(c.tm));
  if (!strcmp(mode, "results")) DO(cvc5_set_logic(c.solver, "QF_UF"));
  else if (!strcmp(mode, "datatype-declarations")) { }
  else if (!strcmp(mode, "datatypes"))
  {
    Cvc5DatatypeDecl decl = declaration(c.tm);
    c.datatype_sort = V(cvc5_mk_dt_sort(c.tm, decl));
    DO(cvc5_dt_decl_release(decl));
  }
  else if (!strncmp(mode, "statistics", 10))
  {
    DO(cvc5_set_logic(c.solver, "QF_UF"));
    Cvc5Result r = V(cvc5_check_sat(c.solver));
    require(V(cvc5_result_is_sat(r)), "expected sat");
    DO(cvc5_result_release(r));
  }
  else if (!strncmp(mode, "synthesis", 9))
  {
    DO(cvc5_set_option(c.solver, "sygus", "true"));
    Cvc5Sort boolean = V(cvc5_get_boolean_sort(c.tm));
    Cvc5Term function = V(cvc5_synth_fun(c.solver, "f", 0, NULL, boolean));
    DO(cvc5_sort_release(boolean));
    DO(cvc5_term_release(function));
    DO(cvc5_add_sygus_constraint(c.solver, c.falsity));
    if (!strcmp(mode, "synthesis-copy")) c.synthesis = V(cvc5_check_synth(c.solver));
  }
  else if (!strcmp(mode, "commands"))
  {
    DO(cvc5_set_logic(c.solver, "QF_UF"));
    c.parser = V(cvc5_parser_new(c.solver, NULL));
  }
  else if (!strcmp(mode, "proofs"))
  {
    DO(cvc5_set_option(c.solver, "produce-proofs", "true"));
    DO(cvc5_assert_formula(c.solver, c.falsity));
    Cvc5Result r = V(cvc5_check_sat(c.solver));
    require(V(cvc5_result_is_unsat(r)), "expected unsat");
    DO(cvc5_result_release(r));
  }
  else if (!strncmp(mode, "grammar", 7))
  {
    DO(cvc5_set_option(c.solver, "sygus", "true"));
    if (!strcmp(mode, "grammar-reuse"))
    {
      c.reused = V(cvc5_mk_grammar(c.solver, 0, NULL, 1, &c.start));
      DO(cvc5_grammar_add_rule(c.reused, c.start, c.truth));
    }
  }
  else require(0, "unknown control");
  return c;
}

static uint64_t step(Control *c)
{
  if (!strcmp(c->mode, "datatype-declarations"))
  {
    Cvc5DatatypeDecl decl = declaration(c->tm);
    DO(cvc5_dt_decl_release(decl));
    return 1;
  }
  if (!strcmp(c->mode, "datatypes"))
  {
    Cvc5Datatype dt = V(cvc5_sort_get_datatype(c->datatype_sort));
    Cvc5Datatype copy = V(cvc5_dt_copy(dt));
    require(!strcmp(V(cvc5_dt_get_name(dt)), "Box"), "datatype name mismatch");
    Cvc5DatatypeConstructor cons = V(cvc5_dt_get_constructor_by_name(copy, "box"));
    Cvc5DatatypeConstructor cons_copy = V(cvc5_dt_cons_copy(cons));
    require(V(cvc5_dt_cons_get_num_selectors(cons)) == 1, "selector count mismatch");
    Cvc5DatatypeSelector sel = V(cvc5_dt_cons_get_selector_by_name(cons_copy, "value"));
    Cvc5DatatypeSelector sel_copy = V(cvc5_dt_sel_copy(sel));
    require(!strcmp(V(cvc5_dt_sel_get_name(sel)), "value"), "selector name mismatch");
    Cvc5Sort sort = V(cvc5_dt_sel_get_codomain_sort(sel_copy));
    require(V(cvc5_sort_is_boolean(sort)), "selector sort mismatch");
    DO(cvc5_sort_release(sort));
    DO(cvc5_dt_sel_release(sel_copy));
    DO(cvc5_dt_sel_release(sel));
    DO(cvc5_dt_cons_release(cons_copy));
    DO(cvc5_dt_cons_release(cons));
    DO(cvc5_dt_release(copy));
    DO(cvc5_dt_release(dt));
    return 1;
  }
  if (!strncmp(c->mode, "statistics", 10))
  {
    int iter = !strcmp(c->mode, "statistics-iter");
    Cvc5Statistics stats = iter ? V(cvc5_term_manager_get_statistics(c->tm)) : V(cvc5_get_statistics(c->solver));
    Cvc5Statistics copied = V(cvc5_stats_copy(stats));
    DO(cvc5_stats_release(stats));
    uint64_t sum = 0;
    if (iter)
    {
      DO(cvc5_stats_iter_init(copied, true, true));
      size_t count = 0;
      while (V(cvc5_stats_iter_has_next(copied)))
      {
        const char *name = NULL;
        Cvc5Stat stat = V(cvc5_stats_iter_next(copied, &name));
        char *key = strdup(name);
        require(key != NULL, "allocation failed");
        sum += strlen(key) + stat_checksum(stat);
        free(key);
        DO(cvc5_stat_release(stat));
        count++;
      }
      require(count > 0, "empty statistics");
    }
    else
    {
      const char *names[] = {"DefaultModel::ee::constantTermsCount", "theory::arith::status::avgUnknownsInARow", "Normalize::pass_time", "resource::steps::resource"};
      for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i)
      {
        Cvc5Stat stat = V(cvc5_stats_get(copied, names[i]));
        sum += stat_checksum(stat);
        DO(cvc5_stat_release(stat));
      }
    }
    DO(cvc5_stats_release(copied));
    return sum;
  }
  if (!strncmp(c->mode, "synthesis", 9))
  {
    Cvc5SynthResult result = c->synthesis ? V(cvc5_synth_result_copy(c->synthesis)) : V(cvc5_check_synth(c->solver));
    Cvc5SynthResult copy = V(cvc5_synth_result_copy(result));
    require(V(cvc5_synth_result_has_no_solution(result)), "expected no solution");
    require(V(cvc5_synth_result_has_no_solution(copy)), "expected copied no solution");
    DO(cvc5_synth_result_release(copy));
    DO(cvc5_synth_result_release(result));
    return 2;
  }
  if (!strcmp(c->mode, "commands"))
  {
    DO(cvc5_parser_set_str_input(c->parser, CVC5_INPUT_LANGUAGE_SMT_LIB_2_6, "(assert true)", "ownership"));
    const char *error = NULL;
    Cvc5Command cmd = V(cvc5_parser_next_command(c->parser, &error));
    require(error == NULL, "parse failed");
    Cvc5Command copied = V(cvc5_cmd_copy(cmd));
    require(!strcmp(V(cvc5_cmd_get_name(cmd)), "assert"), "command name mismatch");
    require(!strcmp(V(cvc5_cmd_get_name(copied)), "assert"), "copied command name mismatch");
    DO(cvc5_cmd_release(copied));
    DO(cvc5_cmd_release(cmd));
    return 2;
  }
  if (!strcmp(c->mode, "results"))
  {
    Cvc5Result r = V(cvc5_check_sat(c->solver));
    Cvc5Result copied = V(cvc5_result_copy(r));
    /* Deliberately retain a reference to validate detector sensitivity. */
    if (c->retain_extra) (void)V(cvc5_result_copy(r));
    require(V(cvc5_result_is_sat(r)), "expected sat");
    require(V(cvc5_result_is_sat(copied)), "expected copied sat");
    DO(cvc5_result_release(copied));
    DO(cvc5_result_release(r));
    return 2;
  }
  if (!strcmp(c->mode, "proofs"))
  {
    size_t count = 0;
    const Cvc5Proof *roots = V(cvc5_get_proof(c->solver, CVC5_PROOF_COMPONENT_FULL, &count));
    require(count > 0, "empty proof array");
    uint64_t checksum = count;
    for (size_t i = 0; i < count; ++i)
    {
      Cvc5Proof root = roots[i];
      Cvc5Proof copied = V(cvc5_proof_copy(root));
      require(V(cvc5_proof_is_equal(copied, root)), "proof copy mismatch");
      Cvc5Term result = V(cvc5_proof_get_result(copied));
      Cvc5Sort sort = V(cvc5_term_get_sort(result));
      require(V(cvc5_sort_is_boolean(sort)), "proof conclusion must be Boolean");
      DO(cvc5_sort_release(sort));
      DO(cvc5_term_release(result));
      size_t child_count = 0;
      const Cvc5Proof *children = V(cvc5_proof_get_children(copied, &child_count));
      require(child_count > 0, "empty proof children");
      checksum += child_count;
      for (size_t j = 0; j < child_count; ++j)
      {
        checksum += V(cvc5_proof_get_rule(children[j]));
        DO(cvc5_proof_release(children[j]));
      }
      DO(cvc5_proof_release(copied));
      DO(cvc5_proof_release(root));
    }
    return checksum;
  }
  Cvc5Grammar grammar = c->reused ? V(cvc5_grammar_copy(c->reused)) : V(cvc5_mk_grammar(c->solver, 0, NULL, 1, &c->start));
  if (strcmp(c->mode, "grammar-empty") && strcmp(c->mode, "grammar-reuse"))
    DO(cvc5_grammar_add_rule(grammar, c->start, c->truth));
  Cvc5Grammar copied = V(cvc5_grammar_copy(grammar));
  if (!strcmp(c->mode, "grammar-empty") || !strcmp(c->mode, "grammar-rules"))
  {
    require(grammar && copied, "null grammar");
    DO(cvc5_grammar_release(copied));
    DO(cvc5_grammar_release(grammar));
    return 1;
  }
  char *original = strdup(V(cvc5_grammar_to_string(grammar)));
  require(original != NULL, "allocation failed");
  const char *shown = V(cvc5_grammar_to_string(copied));
  require(!strcmp(original, shown), "grammar copy mismatch");
  require(strstr(shown, "Γ") && strstr(shown, "true"), "grammar text mismatch");
  uint64_t size = strlen(shown);
  free(original);
  DO(cvc5_grammar_release(copied));
  DO(cvc5_grammar_release(grammar));
  return size;
}

static void destroy(Control *c)
{
  if (c->synthesis) DO(cvc5_synth_result_release(c->synthesis));
  if (c->datatype_sort) DO(cvc5_sort_release(c->datatype_sort));
  if (c->parser) DO(cvc5_parser_delete(c->parser));
  if (c->reused) DO(cvc5_grammar_release(c->reused));
  DO(cvc5_term_release(c->start));
  DO(cvc5_term_release(c->truth));
  DO(cvc5_term_release(c->falsity));
  DO(cvc5_delete(c->solver));
  DO(cvc5_term_manager_delete(c->tm));
}

static uint64_t iteration(Control *c, int round)
{
  if (!round) return step(c);
  Control temporary = create(c->mode, c->retain_extra);
  uint64_t sum = step(&temporary);
  destroy(&temporary);
  return sum;
}

int main(int argc, char **argv)
{
  require(argc == 7, "expected: mode operations warmup samples.tsv retain_extra live|round");
  uint64_t count = strtoull(argv[2], NULL, 10), warmup = strtoull(argv[3], NULL, 10);
  require(count > 0, "invalid operation count");
  const char *path = argv[4], *trace_path = getenv("CVC5_BINDING_TRACE");
  if (trace_path) { trace = fopen(trace_path, "w"); require(trace != NULL, "open trace failed"); }
  require(!strcmp(argv[6], "live") || !strcmp(argv[6], "round"), "invalid lifetime");
  int round = !strcmp(argv[6], "round");
  Control c = {.mode = argv[1], .retain_extra = atoi(argv[5])};
  if (!round) c = create(c.mode, c.retain_extra);
  for (uint64_t i = 0; i < warmup; ++i) (void)iteration(&c, round);
  save_maps(path);
  FILE *out = fopen(path, "w");
  require(out != NULL, "open checkpoint failed");
  fprintf(out, "phase\toperations\telapsed_ns\trss_kib\tchecksum\n");
  require(fclose(out) == 0, "close checkpoint failed");
  uint64_t start = now(), checksum = 0, interval = count / 20;
  if (!interval) interval = 1;
  sample(path, 0, 0, 0, 0);
  for (uint64_t i = 0; i < count; ++i)
  {
    checksum += iteration(&c, round);
    if ((i + 1) % interval == 0 || i + 1 == count) sample(path, 1, i + 1, now() - start, checksum);
  }
  if (!round)
  {
    require(strlen(V(cvc5_get_version(c.solver))) > 0, "missing version");
    destroy(&c);
  }
  sample(path, 2, count, 0, 0);
  if (trace) require(fclose(trace) == 0, "close trace failed");
  printf("completed %" PRIu64 " operations\n", count);
}
