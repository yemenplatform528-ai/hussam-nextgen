from app.hus.compiler import compile_source, HUSCompileError
from app.hus.parser import parse, HUSParseError

SOURCE='''
// HUS-01 example
module shop version "1.0" {
  organization code = shop name = "Shop";
  domain retail {
    engine = retail;
    capabilities = [catalog.read, catalog.write, register.open];
    name = "Retail";
    enabled = true;
  }
  workflow sale {
    trigger = sale.created;
    step confirm {
      action = commerce.confirm;
      approval;
    }
  }
  policy approval_required = [commerce.confirm];
  policy allowed_roles = [admin];
  metadata country = "YE";
}
'''

def test_parse_builds_ast():
    ast=parse(SOURCE)
    assert ast.name=='shop' and ast.version=='1.0'
    assert ast.domains[0].engine=='retail'
    assert ast.workflows[0].steps[0].requires_approval is True

def test_compile_source_is_deterministic():
    a=compile_source(SOURCE); b=compile_source(SOURCE.replace('// HUS-01 example\n',''))
    assert a['ast_hash']==b['ast_hash']
    assert a['contract_hash']==b['contract_hash']

def test_unknown_capability_rejected_semantically():
    bad=SOURCE.replace('catalog.write','not.real')
    try: compile_source(bad)
    except HUSCompileError as e: assert 'unsupported_capability' in str(e)
    else: raise AssertionError('expected semantic rejection')

def test_unknown_action_rejected():
    bad=SOURCE.replace('commerce.confirm','commerce.nope')
    try: compile_source(bad)
    except HUSCompileError as e: assert 'action_not_allowed' in str(e)
    else: raise AssertionError('expected semantic rejection')

def test_syntax_error_has_source_location():
    try: parse('module shop version "1.0" {')
    except (HUSParseError, Exception) as e:
        assert hasattr(e,'token')
    else: raise AssertionError('expected parse failure')

def test_legacy_compile_spec_remains_available():
    from app.hus.compiler import compile_spec
    assert compile_spec({'spec_version':'1.0','organization':{'code':'x','name':'X'},'domains':[],'workflows':[]})['contract_hash']
