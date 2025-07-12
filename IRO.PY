from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def dashboard():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>IRO^PE Dashboard</title>
    </head>
    <body>
        <header>
            <h1>Welcome to IRO^PE</h1>
            <nav>
                <a href="#">Finance</a> |
                <a href="#">Real Estate</a> |
                <a href="#">Upload</a>
            </nav>
        </header>
        <main>
            <p>This is your all-in-one dashboard command center.</p>
        </main>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == '__main__':
    app.run(debug=True)