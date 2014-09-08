// Scrapes twitter users' follows. With great power comes great responsibility Runs on Casper.js (Phantom JS).

// Define a twitter ID to look up.
var twitterId = 'ChaptrApp';

// Define your own e-mail and password to get access to Twitter
var email = 'YourEmail';
var auth = 'YourPassword';

// Define a selector to look for before doing an action.
var findSelector = '.GridTimeline-items';

var urls = [];

var links = [];
var casper = require('casper').create();

function getLinks() {
    var links = document.querySelectorAll('div.ProfileCard a.ProfileCard-screennameLink');

    return Array.prototype.map.call(links, function(e) {

        // Return all of these links
        return e.getAttribute('href');
    });
}

// Start at twitter.com with the defined twitter id
casper.start('http://twitter.com/' + twitterId + '/following', function() {

      // Log the site title
      this.echo(this.getTitle());

      // Log the starting URL
      console.log('Starting location is ' + this.getCurrentUrl());
});

casper.then(function() {

      // Sign In To Twitter. Be careful not to abuse this or we run into the captcha.
      // TODO figure out how to run this overtime without getting caught.
      this.fillSelectors('form.signin', {
          'input[name="session[username_or_email]"]':    email,
          'input[name="session[password]"]':             auth
      }, true);
});

casper.then(function() {

    // Log the new URL
    console.log('Authentication ok, new location is ' + this.getCurrentUrl());

    // Log Error if we hit the captcha
    if (/captcha/.test(this.getCurrentUrl())) {
        console.log('Please login and confirm your captcha.');
    }
});

casper.waitForSelector('.GridTimeline-items', function() {

      // Log that we found the right selector to capture. This is looking for the follower grid on the mid 2014 Twitter Redesign.
      console.log('.GridTimeline-items' + ' is loaded.');

      // Screenshot
      this.captureSelector('timeline.png', 'div.GridTimeline-items');

      // Grab First Links
      this.emit('results.log');
});

function tryAndScroll(casper) {
    casper.waitFor(function() {
        this.page.scrollPosition = { top: this.page.scrollPosition["top"] + 3333, left: 0 };
        return true;
    }, function() {
        var info = this.getElementInfo('div.GridTimeline-footerIcon span.Icon--logo');

        // Recursively scroll until the bottom nav is visible.
        if (info["visible"] !== true) {
            this.waitWhileVisible('div.GridTimeline-footerIcon span.Icon--logo', function () {
                this.emit('results.loaded');
                this.emit('results.log');

            // We're still missing the last few rows of people.
            }, function () {
                this.echo('Next results not loaded');
            }, 5000);
        }
    }, function() {
        this.echo("Scrolling failed. Sorry.").exit();
    }, 500);
}

casper.on('results.loaded', function () {

    this.echo('Scrollin');

    // Call Scroll Function
    tryAndScroll(this);
});

casper.on('results.log', function () {
    // Grab Additional Links
    links = this.evaluate(getLinks);
});

casper.then(function() {
    tryAndScroll(this);
});

// Snippet from: https://www.andykelk.net/tech/web-scraping-with-casperjs
casper.run(function() {

    // Run through our array to format the JSON for D3
    for (i in links) {
      links[i] = "{'name':" + "'" + links[i] + "'" + ", 'group': 2}";
    }

    nodeLinks = [];

    var min;

    for (i in links) {
      // A crude buffer
      min = Math.min((parseInt(i) * 10), 450);

      nodeLinks.push("{'source':" + (parseInt(i) + 1) + "," + "'target':0,'value':" + min + "}");
    }

    // Format it
    var re = /\//g;
    var name = links.join(' ');

    // Change to a string
    var jsonString = JSON.stringify(links);

    // Do some gross replaces just for D3
    var finalJson = ("\"nodes\" :[ " + "{'name': '" + twitterId + "', " + "'group':1}\", " + jsonString.replace(re," ") + " ]");

    finalJson = finalJson.replace(/"\{/g,"{");
    finalJson = finalJson.replace(/\}"/g,"}");

    finalJson = finalJson.replace(/\[\{/g,"{");
    finalJson = finalJson.replace(/\}\]/g,"}");

    finalJson = "{ " + finalJson + ", " + "\n \n'links':[" + nodeLinks.toString() + "]" + " }";

    finalJson = finalJson.replace(/'/g,"\"");

    console.log(finalJson);

    // Export as JSON
    require('fs').write("finalJson.json", finalJson, 'w');

    // Close Casper
    this.exit();
});/**
 * Created by rmaja on 12/08/14.
 */
