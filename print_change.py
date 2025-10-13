import sys

class NewStdout:
    def __init__(self, original, path):
        self.original = original
        self.write_path = path

    def flush(self):
        self.original.flush()

    def write(self, text):
        with open(self.write_path, 'a', encoding='utf-8') as file:
            file.write(text)

    def clear(self):
                with open(self.write_path, 'w', encoding='utf-8') as file:
                     pass

sys.stdout = NewStdout(sys.stdout, r'C:\Users\thoma\OneDrive\Dokumenty\code\Tutorials\html-css-javascript-course\javascript-amazon-project\test.txt')