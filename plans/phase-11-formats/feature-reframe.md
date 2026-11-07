# Reframe

Done when:
- [x] a 16:9 program becomes any target aspect by a crop that follows the face track (smoothed, holds still while
      the face moves little, eases on jump cuts), never cutting the face; punch-ins keep working
- [ ] a source already in the target aspect passes through untouched; a vertical source in a 16:9 output is
      refused with a clear error
- [x] the crop path is cached by face track + aspect, and shown on a check sheet

(open: native vertical sources need the landscape assumptions removed from ingest proxy, faces, program
sizes and placement first; done together with feature-layout. Measured on the Telegram talk: face inside the
crop at every one of 3242 points for 9:16, 4:5 and 1:1; 9:16 moves on 47 steps, 4:5 and 1:1 on 6.)
