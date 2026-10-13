/* Independent execution of replayable binding operations; values come from C. */
#include "support.h"

static Cvc5* solver_new(Cvc5TermManager* tm)
{
  Cvc5* solver = V(cvc5_new(tm));
  DO(cvc5_set_logic(solver, "QF_LIA"));
  DO(cvc5_set_option(solver, "produce-models", "true"));
  return solver;
}

static void values(size_t step, char op, Cvc5Term* terms, size_t size)
{
  printf("%zu %c [", step, op);
  for (size_t i = 0; i < size; ++i)
    printf("%s%s", i ? "," : "", V(cvc5_term_get_integer_value(terms[i])));
  puts("]");
}

static void reject(Cvc5TermManager* tm, Cvc5* solver, Cvc5Term term, int kind, uint32_t width, const char* overflow)
{
  Cvc5Term held = V(cvc5_term_copy(term));
  Cvc5Term boolean = V(cvc5_mk_true(tm));
  Cvc5Term args[] = {held, boolean};
  Cvc5Term unexpected = NULL;
  switch (kind)
  {
    case 0: unexpected = cvc5_mk_integer(tm, "not_an_integer"); break;
    case 1: unexpected = cvc5_mk_real(tm, "1/0"); break;
    case 2: unexpected = cvc5_mk_bv(tm, width, overflow, 10); break;
    case 3: (void)cvc5_term_get_boolean_value(held); break;
    case 4: cvc5_assert_formula(solver, held); break;
    case 5: unexpected = cvc5_mk_term(tm, CVC5_KIND_ADD, 2, args); break;
    default: require(0, "unknown error operation");
  }
  require(cvc5_has_error(), "invalid operation unexpectedly accepted");
  require(strlen(cvc5_get_error_message()) > 0, "empty error diagnostic");
  cvc5_reset_error();
  require(unexpected == NULL, "error returned an unexpected reference");
  DO(cvc5_term_release(boolean)); DO(cvc5_term_release(held));
}

int main(int argc, char** argv)
{
  require(argc == 3, "expected input and mapping stem");
  setvbuf(stdout, NULL, _IOLBF, 0);
  FILE* file = fopen(argv[1], "r");
  require(file != NULL, "input missing");
  Cvc5TermManager* tm = V(cvc5_term_manager_new());
  Cvc5* solver = solver_new(tm);
  Cvc5Term slots[8], saved[32];
  size_t saved_size = 0, step = 0;
  for (size_t i = 0; i < 8; ++i) slots[i] = V(cvc5_mk_integer_int64(tm, 0));
  char* line = NULL;
  size_t capacity = 0;
  while (getline(&line, &capacity, file) >= 0)
  {
    char* parts[40];
    size_t count = 0;
    for (char* p = strtok(line, " \n"); p; p = strtok(NULL, " \n"))
    {
      require(count < 40, "too many fields"); parts[count++] = p;
    }
    if (!count) continue;
    char op = parts[0][0];
    int a = count > 1 && strchr("ICABVEP", op) ? atoi(parts[1]) : 0;
    int b = count > 2 && strchr("CABEP", op) ? atoi(parts[2]) : 0;
    Cvc5Term term;
    switch (op)
    {
      case 'I':
        require(count == 4 && a >= 0 && a < 8, "invalid integer input");
        term = atoi(parts[3]) == 2 ? V(cvc5_mk_integer_int64(tm, strtoll(parts[2], NULL, 10))) : V(cvc5_mk_integer(tm, parts[2]));
        DO(cvc5_term_release(slots[a])); slots[a] = term;
        printf("%zu I %s\n", step, V(cvc5_term_get_integer_value(term)));
        break;
      case 'C':
        require(count == 3 && a >= 0 && a < 8 && b >= 0 && b < 8, "invalid copy input");
        term = V(cvc5_term_copy(slots[b]));
        DO(cvc5_term_release(slots[a])); slots[a] = term;
        printf("%zu C %s\n", step, V(cvc5_term_get_integer_value(term)));
        break;
      case 'A':
      {
        require(count == 5 && a >= 0 && a < 8 && b >= 0 && b < 8, "invalid arithmetic input");
        int c = atoi(parts[3]); require(c >= 0 && c < 8, "invalid arithmetic slot");
        Cvc5Term children[] = {slots[b], slots[c]};
        Cvc5Term expr = V(cvc5_mk_term(tm, atoi(parts[4]) ? CVC5_KIND_SUB : CVC5_KIND_ADD, 2, children));
        term = V(cvc5_simplify(solver, expr, false));
        DO(cvc5_term_release(expr)); DO(cvc5_term_release(slots[a])); slots[a] = term;
        printf("%zu A %s\n", step, V(cvc5_term_get_integer_value(term)));
        break;
      }
      case 'Q':
      {
        require(count == 4, "invalid rational input");
        char rational[1024];
        require(snprintf(rational, sizeof(rational), "%s/%s", parts[1], parts[2]) < (int)sizeof(rational), "oversized rational");
        term = V(cvc5_mk_real(tm, rational));
        printf("%zu Q %s\n", step, V(cvc5_term_get_real_value(term)));
        DO(cvc5_term_release(term)); break;
      }
      case 'B':
        require(count == 5 && a > 0 && a <= 257, "invalid bit-vector input");
        term = V(cvc5_mk_bv(tm, (uint32_t)a, parts[3], (uint32_t)b));
        printf("%zu B %s\n", step, V(cvc5_term_get_bv_value(term, 10)));
        DO(cvc5_term_release(term)); break;
      case 'V':
      {
        require(count == (size_t)a + 2 && a >= 0 && a <= 32, "invalid array input");
        for (size_t i = 0; i < saved_size; ++i) DO(cvc5_term_release(saved[i]));
        Cvc5Term inputs[32];
        for (int i = 0; i < a; ++i)
        {
          int slot = atoi(parts[i + 2]); require(slot >= 0 && slot < 8, "invalid array slot");
          inputs[i] = slots[slot];
        }
        Cvc5Result result = V(cvc5_check_sat(solver));
        require(V(cvc5_result_is_sat(result)), "model not sat"); DO(cvc5_result_release(result));
        const Cvc5Term* output = V(cvc5_get_values(solver, (size_t)a, inputs, &saved_size));
        require(saved_size == (size_t)a, "wrong result length");
        if (saved_size) memcpy(saved, output, saved_size * sizeof(*saved));
        /* Invalidate the borrowed output buffer immediately after adopting it. */
        size_t later_size = 0;
        const Cvc5Term* later = V(cvc5_get_values(solver, 1, slots, &later_size));
        require(later_size == 1, "replacement output length");
        DO(cvc5_term_release(later[0]));
        values(step, op, saved, saved_size); break;
      }
      case 'G': values(step, op, saved, saved_size); break;
      case 'R':
      {
        Cvc5* next = solver_new(tm);
        DO(cvc5_delete(solver)); solver = next;
        printf("%zu R reset\n", step); break;
      }
      case 'E':
        require(count == 5 && b >= 0 && b < 8, "invalid error input");
        reject(tm, solver, slots[b], a, (uint32_t)atoi(parts[3]), parts[4]);
        printf("%zu E recovered %s\n", step, V(cvc5_term_get_integer_value(slots[b]))); break;
      case 'P':
      {
        require(count == 3 && a >= 0 && a < 8 && b >= 0 && b < 8, "invalid comparison input");
        bool eq = V(cvc5_term_is_equal(slots[a], slots[b]));
        int64_t ab = V(cvc5_term_compare(slots[a], slots[b])), ba = V(cvc5_term_compare(slots[b], slots[a]));
        require((ab == 0) == eq && (ab < 0) == (ba > 0) && (ab > 0) == (ba < 0), "comparison invariant");
        require(!eq || V(cvc5_term_hash(slots[a])) == V(cvc5_term_hash(slots[b])), "hash invariant");
        printf("%zu P %d\n", step, eq); break;
      }
      default: require(0, "unknown operation");
    }
    require(!cvc5_has_error(), "uncleared native error");
    ++step;
  }
  require(!ferror(file), "input read failed");
  free(line); fclose(file);
  for (size_t i = 0; i < saved_size; ++i) DO(cvc5_term_release(saved[i]));
  for (size_t i = 0; i < 8; ++i) DO(cvc5_term_release(slots[i]));
  DO(cvc5_delete(solver)); DO(cvc5_term_manager_delete(tm));
  save_maps(argv[2]);
  puts("sequence passed");
}
