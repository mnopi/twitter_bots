var casper = require('casper').create({
    viewportSize: {width: 1024, height: 768}
    //verbose: true,
    //logLevel: "debug",
    //pageSettings: {
    //    userAgent: this.cli.get('useragent')
    //}
});
var output = {};

casper.start();

casper.userAgent(casper.cli.get('useragent'));

casper.thenOpen('http://whatsmyuseragent.com', function(){
    output.title = this.getTitle();
    output.userAgent = this.cli.get('useragent');
    output.screenshots = this.cli.get('screenshots');
    output.tweetmsg = this.cli.get('tweetmsg');
    //this.echo('Screenshots dir: ' + this.cli.get('screenshots'));
    this.capture(this.cli.get('screenshots') + 'myuseragent.png');
});

//casper.waitForSelector('#ip-box .the-ip', function(){
//    output.ip = this.fetchText('#ip-box .the-ip');
//});

//casper.wait(3000, function(){
    //this.echo('Waited 3 secs');
//});

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