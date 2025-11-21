
import processing.video.*;
import oscP5.*;
import netP5.*;

int numPixelsOrig;
int numPixels;

int boxWidth = 16;
int boxHeight = 12;

int numHoriz = 640/boxWidth;
int numVert = 480/boxHeight;

color[] downPix = new color[numHoriz * numVert];

Capture video;

OscP5 oscP5;
NetAddress dest;

void setup() {
  size(640, 480);

  video = new Capture(this, 640, 480);
    
  // Start capturing the images from the camera
  video.start();
    
  numPixelsOrig = video.width * video.height;
  noStroke();

  /* start oscP5, listening for incoming messages at port 12000 */
  oscP5 = new OscP5(this,9000);
  dest = new NetAddress("127.0.0.1",6448);
}
 
void captureEvent(Capture c) {
  c.read();
}

void draw() {
  background(0);
  
  video.loadPixels(); // Make the pixels of video available
  int boxNum = 0;
  int tot = boxWidth*boxHeight;
  for (int x = 0; x < 640; x += boxWidth) {
     for (int y = 0; y < 480; y += boxHeight) {
        float red = 0, green = 0, blue = 0;
        
        
        for (int i = 0; i < boxWidth; i++) {
           for (int j = 0; j < boxHeight; j++) {
              int index = (x + i) + (y + j) * 640;
              red += (video.pixels[index] >> 16) & 0xff;
              green += (video.pixels[index] >> 8) & 0xff;
              blue += video.pixels[index] & 0xff;
           } 
        }
       downPix[boxNum] =  color(red/tot, green/tot, blue/tot);
       fill(downPix[boxNum]);
       rect(x, y, boxWidth, boxHeight);
       boxNum++;
     } 
  }
  
  if(frameCount % 2 == 0)
    sendOsc(downPix);
  
  fill(255);
  text("Sending 100 inputs to port 6448 using message /wek/inputs", 10, 10);

}

void sendOsc(int[] px) {
  OscMessage msg = new OscMessage("/wek/inputs");
  for (int i = 0; i < px.length; i++) {
    msg.add(float(px[i])); 
  }
  oscP5.send(msg, dest);
}
