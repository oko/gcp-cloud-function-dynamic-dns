import click
import flask
from dynamic_dns import dynamic_dns

app = flask.Flask(__name__)

@app.route('/dynamic_dns')
def testroute():
    return dynamic_dns(flask.request)



if __name__ == "__main__":
    app.run('::', 8080, debug=True)