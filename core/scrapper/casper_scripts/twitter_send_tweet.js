var casper = require('casper').create({
    viewportSize: {width: 1024, height: 768}
    //verbose: true,
    //logLevel: "debug"
    //pageSettings: {
    //    userAgent: this.cli.get('useragent')
    //}
});

var mouse = require("mouse").create(casper);

var utils = require('utils');

var output = {
    errors: [],
    not_found_el_css: null
};

var capture_index = 0;

function getRandomIntFromRange(min, max) {
  return Math.round(Math.random() * (max - min)) + min;
}

function capture(name){
    capture_index++;
    casper.capture(casper.cli.get('screenshots') + capture_index + '_' + name + '.png');
}

function click(el){
    check_el_css(el);
    casper.mouse.move(el);
    casper.mouse.click(el);
}

function check_el_css(el)
{
    if (!casper.visible(el)){
        output.errors.not_found_el_css = el;
        exit();
    }
}

function write_tweet_delayed_keys()
{
    var tweet_msg = casper.cli.get('tweetmsg');
    // se escribe el tweet
    for (var i in tweet_msg) {
        var current_letter = tweet_msg[i],
            delay = getRandomIntFromRange(200, 600); // entre 200 y 600 ms se pulsan teclas
        casper.wait(
            delay,
            (function (i, current_letter) {
                return function () {
                    casper.sendKeys(tweet_dialog_css, current_letter, {keepFocus: true});
                    //casper.echo('Sent: ' + current_letter);
                };
            })(i, current_letter)
        );
    }
}

function write_tweet()
{
    var tweet_msg = casper.cli.get('tweetmsg');
    casper.sendKeys(tweet_dialog_css, tweet_msg, {keepFocus: true});
}

function print_output()
{
    casper.echo(JSON.stringify(output));
}

function exit()
{
    print_output();
    casper.exit();
}

casper.start();

casper.userAgent(casper.cli.get('useragent'));

casper.thenOpen('https://twitter.com', function () {

    // limpiamos lo que hubiera en localstorage
    this.evaluate(function () {
        localStorage.clear();
    }, {});

    if (!this.getHTML('body'))
    {
        output.errors.push('internet_connection_error');
        capture('internet_connection_error');
        exit();
    }
    else
    {
        capture('page_loaded');
    }
});

var tweet_btn_css = '#global-new-tweet-button';
casper.waitUntilVisible(tweet_btn_css,
    function then() {
        click(tweet_btn_css);
    },
    function onTimeout() {
        capture('not_logged_in');
        output.errors.push('not_logged_in');
        exit();
    }
);

// escribimos el tweet
var tweet_dialog_css = '#global-tweet-dialog-dialog div.tweet-content';
casper.waitUntilVisible(tweet_dialog_css,
    function then() {
        capture('tweet_dialog_loaded');
    }
);

casper.wait(getRandomIntFromRange(1000, 2000));
casper.then(write_tweet);
casper.wait(getRandomIntFromRange(7000, 15000));

// una vez escrito el tweet pulsamos el botón de enviar el tweet
casper.wait(getRandomIntFromRange(800, 2000), function () {
    click('#global-tweet-dialog-dialog .tweet-button button');
});

// esperamos a ver si se envió bien o no
casper.wait(getRandomIntFromRange(5000, 10000),
    function then() {
        capture('clicked_send_tweet_btn');

        var msg_drawer = '#message-drawer .message-text';
        if (this.visible(msg_drawer)) {
            msg_drawer_text = this.fetchText(msg_drawer).toLowerCase();
            if (msg_drawer_text.indexOf("already sent") >= 0) {
                output.errors.push('tweet_already_sent');
                capture('tweet_already_sent');
            }
            else if (msg_drawer_text.indexOf("suspended") >= 0) {
                output.errors.push('account_suspended');
                capture('account_suspended')
            }
        }
    }
);

casper.then(function () {
    this.echo(JSON.stringify(output));
});

casper.run();