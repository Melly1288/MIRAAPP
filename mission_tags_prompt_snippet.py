MISSION_TAGS_PROMPT_ADDITION = """
MISSION TAGGING (additive - does not affect rating/verdict/next_action):
In addition to the fields above, add one more field: "mission_tags", an
array of zero or more strings from the controlled list below. Include a
tag ONLY if that specific visual quality is clearly present in the photo -
do not force a tag to apply. It is normal and expected for most photos to
match only 1-3 tags, and completely fine for a photo to match zero tags.
This field is used for a separate gamified mission-tracking feature and
must never influence your rating, verdict, or next_action - grade the
photo's quality exactly as you already do, then separately note which of
these descriptive tags apply, independent of whether the photo is good.

Available tags (tag: what it means):
- perfectly_round: Find something perfectly round
- belongs_together: Two objects that belong together
- perfect_pair: Two identical objects
- smallest_thing_here: The smallest object you can find
- multiples: Three or more of the same object
- walked_past_daily: Something people walk past every day
- texture_hunter: Something rough to the touch
- tiny_world: Something so small you almost missed it
- one_of_a_kind: Something that looks unique in its surroundings
- worn_with_age: Something that shows its age
- stacked_up: Things stacked on top of each other
- something_soft: Something soft to the touch
- everyday_hero: An object you use every day but never photograph
- off_centre: Place your subject off-centre
- fill_the_frame: Get so close your subject fills the whole photo
- repeating_pattern: Find a repeating pattern
- center_stage: Put your subject dead center on purpose
- doorway_frame: Frame a scene using a door or window
- leading_lines: Find lines that lead the eye somewhere
- through_the_frame: Photograph through something (window, gap, branches)
- negative_space: Use empty space to make your subject stand out
- diagonal_story: Find a diagonal line running through your shot
- framed_naturally: Use a natural frame (doorway, branches, arch)
- balance_act: Balance two subjects on either side of the frame
- curved_path: Find a curve that leads through the scene
- tiny_subject_big_space: A small subject in a huge open space
- shadow_play: Interesting shadows
- golden_warmth: Warm sunlight on something
- window_glow: Soft light coming through a window
- cool_blue: Cool-toned light (shade, evening, overcast)
- mirror_light: A reflection of light
- backlit: Shoot your subject with light behind it
- high_contrast: Strong light and dark in one shot
- long_shadow: A shadow longer than its subject
- dappled_light: Light filtering through leaves or gaps
- glow_from_within: Something lit from inside (lamp, screen, candle)
- flat_light: A subject with almost no shadow at all
- light_and_texture: Light that reveals a surface's texture
- light_through_fabric: Light passing through curtains or cloth
- one_dominant_colour: A scene ruled by one colour
- trio: Three colours together in one shot
- warm_only: Only warm colours (red, orange, yellow)
- cool_only: Only cool colours (blue, green, purple)
- nature_s_palette: Colours found only in nature
- clash: Two colours that clash
- almost_monochrome: A scene that's almost black and white
- pop_of_colour: One colour standing out from a dull background
- muted_tones: Soft, faded, dusty colours
- skin_of_the_city: The dominant colour of a building or wall
- faded_paint: Colour that's peeling or worn
- colour_echo: A colour that repeats twice in the same frame
- skin_tones: A portrait where skin tone is the warmest thing in frame
- a_peaceful_moment: Capture calm
- comfort_object: Something that brings comfort
- feels_hopeful: A scene that feels hopeful
- new_beginning: A scene that feels like a start
- something_waiting: An object or place that feels like it's waiting for someone
- evidence_someone_was_here: Signs that someone was recently in this spot
- unfinished_business: Something left incomplete
- someone_s_routine: Evidence of a daily habit or routine
- passing_time: Something that shows the passage of time
- everyday_ritual: A small, repeated daily action caught in a photo
- the_journey: A path, road, or route that suggests a journey
- left_a_mark: Something that has visibly changed its surroundings
- the_wait: Something in the middle of waiting for something else
- windblown: Something moved by the wind
- rolling_wheels: Something with wheels in motion
- swaying: Something swaying gently
- drift: Something drifting slowly (leaf, cloud, boat)
- full_speed: The fastest thing you can find nearby
- freeze_frame: Freeze something in motion
- water_in_motion: Moving water
- trail_of_motion: A trail left behind by movement
- spinning: Something spinning
- ripple_effect: A ripple spreading outward
- gust: Evidence of a sudden gust of wind
- flow: Something flowing steadily (traffic, crowd, stream)
- everyday_blur: Motion blur from something ordinary (fan, pet, traffic)
- ground_level: Shoot from ground level
- straight_down: Look straight down and shoot
- straight_up: Look almost straight up
- worm_s_eye: Shoot upward from as low as possible
- squeeze_through: Shoot from a tight or unusual gap
- giant_small_thing: Make something small look huge
- partial_view: Photograph only part of something
- peek_through: Peek through a small gap
- behind_the_scenes: Photograph the back or underside of something
- tilted_world: Shoot at a deliberate tilt
- close_enough_to_touch: Get closer than feels normal
- far_enough_to_vanish: Make your subject tiny in a huge scene
- through_glass: Shoot through glass or a reflective surface
- calm: Capture calm
- comfort: Capture comfort
- joy: Capture joy
- playfulness: Capture playfulness
- curiosity: Capture curiosity
- mystery: Capture mystery
- energy: Capture energy
- fresh_start: Capture a fresh start
- anticipation: Capture anticipation
- wonder: Capture wonder
- safety: Capture the feeling of being safe
- home: Capture the feeling of home
- stillness: Capture stillness
"""

# Updated JSON schema example to show Claude in the prompt:
MISSION_TAGS_SCHEMA_NOTE = '  "mission_tags": [string, ...]'