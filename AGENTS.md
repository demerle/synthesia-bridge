You have passwordless sudo priveleges inside of a docker container. Dont be afraid to use sudo commands.

As a coding agent, there are a clear rules that you should operate under.

When generating plans or mapping out a project, never estimate how much time it will take.


When generating tests and test cases, always prioritize end to end testing over smaller unit tests. It is far more important that the errors are caught during development than if the tests are "atomic".

Also, when it comes to testing, always prefer NOT to use "Mocks" or "Fakes" of things unless ABSOLUTELY NECESSARY. For example, if a function needs a pdf object as an input, use a local "dummy.pdf" or something instead using a mock library. This will give more realistic output/errors when running the tests, catching more edge cases.

If you are writing Python code, prioritize readability of the code over trying to write "one-liners". To be specific, never use dictionary comprehension at all, and for list comphrehensions, only use it if the meaning is extremely simple in obvious.

