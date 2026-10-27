# Ruby

A pattern rule and its test file. Each test case covers one branch, named by its
comment.

A convention: instance variables are written only in `initialize`, a setter, or a
memoization. RuboCop has no such cop, so without codeguard this is a custom cop.

## `.codeguard/rules/pattern/ivars-written-in-initialize.yml`

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

## `.codeguard/rule-tests/ivars-written-in-initialize-test.yml`

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
