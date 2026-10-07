# Example rules

One rule per language, each with its test file. Test cases cover one branch each,
named by their comment.

## Python

A convention: concrete models inherit `BaseModel`; abstract mixins are skipped.

### `.codeguard/rules/pattern/models-inherit-base-model.yml`

```yaml
id: models-inherit-base-model
language: python
severity: error
message: Concrete models inherit BaseModel.
note: |
  BaseModel adds the shared primary key and timestamps. Change the superclass to
  BaseModel. Abstract mixins (`class Meta: abstract = True`) are skipped.
rule:
  kind: class_definition
  has:
    field: superclasses
    has:
      pattern: Model
  not:
    has:
      field: body
      has:
        kind: class_definition
        all:
          - has: { field: name, regex: ^Meta$ }
          - has: { field: body, stopBy: end, pattern: abstract = True }
```

### `.codeguard/rule-tests/pattern/models-inherit-base-model-test.yml`

```yaml
id: models-inherit-base-model
valid:
  # Concrete model on BaseModel
  - |
    class ExampleModel(BaseModel):
        name = CharField()

  # Abstract mixin is skipped
  - |
    class ExampleMixin(Model):
        class Meta:
            abstract = True

invalid:
  # Concrete model on Model
  - |
    class ExampleModel(Model):
        name = CharField()

  # Meta without abstract is still concrete
  - |
    class ExampleModel(Model):
        class Meta:
            ordering = ["name"]
```

## TypeScript

A convention: promises are awaited, not chained with `.then` or `.catch`.

### `.codeguard/rules/pattern/await-promises.yml`

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

### `.codeguard/rule-tests/pattern/await-promises-test.yml`

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

## Ruby

A convention: instance variables are written only in `initialize`, a setter, or a
memoization. RuboCop has no such cop, so without codeguard this is a custom cop.

### `.codeguard/rules/pattern/ivars-written-in-initialize.yml`

```yaml
id: ivars-written-in-initialize
language: ruby
severity: error
message: Write instance variables only in initialize, a setter, or a memoization.
note: |
  A method that assigns state directly hides a write from the class's interface.
  Declare an attr_writer and assign with `self.name = value`. Memoization
  (`@name ||= ...`) is allowed.
rule:
  kind: assignment
  has:
    field: left
    kind: instance_variable
  inside:
    kind: method
    stopBy: end
    not:
      any:
        - has: { field: name, regex: ^initialize$ }
        - has: { field: name, kind: setter }
```

### `.codeguard/rule-tests/pattern/ivars-written-in-initialize-test.yml`

```yaml
id: ivars-written-in-initialize
valid:
  # Assignment in initialize
  - |
    class Thing
      def initialize(name)
        @name = name
      end
    end

  # Assignment in a setter
  - |
    class Thing
      def name=(value)
        @name = value
      end
    end

  # Memoization
  - |
    class Thing
      def total
        @total ||= compute_total
      end
    end

invalid:
  # Assignment in another method
  - |
    class Thing
      def load
        @loaded = true
      end
    end
```
