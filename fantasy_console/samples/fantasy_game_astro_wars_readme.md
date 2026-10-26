# Astro Wars - Classic Space Shooter

A minimal old-school space shooter game for the FantasyUW console, inspired by classic arcade games like Galaga and Space Invaders.

## Features

- **Player Ship**: Move left/right and shoot bullets upward
- **Enemy Ships**: Spawn from the top and move downward
- **Enemy AI**: Enemies occasionally shoot back
- **Collision Detection**: Bullets destroy enemies, enemy bullets destroy player
- **Score System**: Earn 10 points per enemy destroyed
- **Star Field**: Simple animated background
- **Pixel Perfect Sprites**: Hand-crafted 8-bit style graphics

## Controls

- **LEFT/RIGHT Arrow Keys**: Move your ship
- **SPACE**: Fire bullets
- **ESCAPE**: Quit game

## How to Run

Install pygame (`pip install -r ../requirements.txt`), then from the `fantasy_console` folder:

```bash
# Compile and run in one step
python fantasy_console.py samples/fantasy_game_astro_wars.uws --fps 60

# Or compile first (writes samples/fantasy_game_astro_wars.asm and _strings.txt), then run
python ../uwscript/uwscript_compiler.py samples/fantasy_game_astro_wars.uws -v
python fantasy_console.py samples/fantasy_game_astro_wars.asm --fps 60
```

## Game Mechanics

### Player
- Green spaceship that moves horizontally at the bottom
- Can fire up to 3 bullets simultaneously
- Destroyed if hit by enemy bullets

### Enemies
- Red alien ships that spawn at the top
- Move downward at constant speed
- Occasionally fire red bullets at the player
- Worth 10 points when destroyed

### Bullets
- Player bullets: Yellow, move upward quickly
- Enemy bullets: Red, move downward
- Bullets are destroyed on impact or when leaving screen

## Technical Details

- **Screen Resolution**: 128x128 pixels
- **Color Palette**: 16-color retro palette
- **Frame Rate**: 60 FPS
- **Sprite Format**: Custom pixel art using the FantasyUW sprite system
- **Programming Language**: UWScript (compiled to UW VM assembly)

## Code Structure

The game is written in UWScript and demonstrates:
- Sprite-based graphics
- Simple game state management
- Collision detection algorithms
- Input handling
- Timer-based enemy spawning
- Score tracking

## Extending the Game

The code is designed to be easily modifiable. You can:

1. **Add More Enemy Types**: Create new sprite arrays and add them to the enemy system
2. **Power-ups**: Add special items that fall from the top
3. **Sound Effects**: Use the `play_tone()` function to add audio
4. **Multiple Lives**: Track player lives and respawn
5. **Levels**: Increase difficulty over time
6. **Better Graphics**: Create larger, more detailed sprites

## Limitations

This is a minimal implementation with:
- Simple collision detection (bounding box)
- Limited number of simultaneous objects
- No sound effects (but easily addable)
- Basic enemy AI

## License

Free to use and modify. Created as a demonstration of the FantasyUW console capabilities.

---

*Enjoy defending Earth from the alien invasion!* 🚀👾