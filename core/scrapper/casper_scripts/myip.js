var casper = require('casper').create({
    viewportSize: {width: 1024, height: 768},
    //verbose: true,
    //logLevel: "debug",
    pageSettings: {
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.97 Safari/537.11"
    }
});

var output = {};


casper.start('http://whatismyip.com', function(){
    output.title = this.getTitle();
    //this.echo('Screenshots dir: ' + this.cli.get('screenshots'));
    this.capture(this.cli.get('screenshots') + '/myip.png');
});

casper.waitForSelector('#ip-box .the-ip', function(){
    output.ip = this.fetchText('#ip-box .the-ip');
});

casper.wait(3000, function(){
    //this.echo('Waited 3 secs')
});

//casper.wait(100000, function() {
//    this.echo("I've waited for a second.");
//});

//casper.thenOpen('http://whatismyip.com', function(){
//});
//
//casper.thenOpen('http://whatsmyuseragent.com', function(){
//    this.capture('/Users/rmaja/myuseragent.png');
//});

casper.then(function(){
    this.echo(JSON.stringify(output));
});

casper.run();