# TypeScript

A pattern rule and its test file. Each test case covers one branch, named by its
comment.

A convention: promises are awaited, not chained with `.then` or `.catch`.

## `.codeguard/rules/pattern/await-promises.yml`

```yaml
id: await-promises
language: typescript
severity: error
message: Await promises instead of chaining .then or .catch.
note: |
  Chained callbacks split the control flow and lose async stack traces. Use await,
  with try/catch for errors.
rule:
  any:
    - pattern: $PROMISE.then($$$ARGS)
    - pattern: $PROMISE.catch($$$ARGS)
```

## `.codeguard/rule-tests/await-promises-test.yml`

```yaml
id: await-promises
valid:
  # Awaited call
  - |
    const thing = await loadThing(id);

  # Awaited call with try/catch
  - |
    try {
      await saveThing(thing);
    } catch (error) {
      reportError(error);
    }

invalid:
  # .then chain
  - |
    loadThing(id).then((thing) => renderThing(thing));

  # .catch chain
  - |
    saveThing(thing).catch((error) => reportError(error));
```
