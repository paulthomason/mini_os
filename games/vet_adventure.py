import time
from PIL import Image, ImageDraw

thread_safe_display = None
fonts = None
exit_cb = None

state = "start"

STEPS = {   'abby_file': {   'choices': [   ('Offer help', 'help_abby'),
                                    ('Back to desk', 'start')],
                     'text': ['She grudgingly', 'files forms.']},
    'alert_vet': {   'choices': [('Back to desk', 'start')],
                     'text': ['Vet appreciates', 'the warning.']},
    'anderson': {   'choices': [   ('Ask for tasks', 'anderson_tasks'),
                                   ('Back to desk', 'start'),
                                   ('Supply orders', 'supply_orders')],
                    'text': ['Dr. Anderson', 'checks in.']},
    'anderson_tasks': {   'choices': [   ('Find Nova', 'find_nova'),
                                         ('Back', 'start'),
                                         ('Staff meeting', 'staff_meeting')],
                          'text': ['She asks you to', 'check on Nova.']},
    'assist_nova': {   'choices': [   ('Back to desk', 'start'),
                                      ('Discuss training', 'training_chat'),
                                      ('Check meds', 'check_meds')],
                       'text': ['Call goes well,', 'Nova relieved.']},
    'assist_surgery': {   'choices': [('Back to desk', 'start')],
                          'text': ['Surgery runs', 'smoothly.']},
    'break_chat': {   'choices': [   ('Plan lunch', 'schedule_lunch'),
                                     ('Back to desk', 'start')],
                      'text': ['Anita shares', 'weekend tales.']},
    'break_room': {   'choices': [   ('Chat coworker', 'break_chat'),
                                     ('Check fridge', 'check_fridge'),
                                     ('Back to desk', 'start')],
                      'text': ['Quick snack in', 'the break room.']},
    'call_client': {   'choices': [   ('Record note', 'record_note'),
                                      ('Back', 'start')],
                       'text': ['You update the', "client's meds."]},
    'call_vet': {   'choices': [   ('Wait', 'wait_vet'),
                                   ('Prep room', 'prep_er_room'),
                                   ('Text update', 'text_update')],
                    'text': ['Anderson is on', 'the way.']},
    'calm_clients': {   'choices': [   ('Catch cat', 'catch_cat'),
                                       ('Back', 'start')],
                        'text': ['Clients wait', 'patiently.']},
    'calm_owner': {   'choices': [   ('Back to desk', 'start'),
                                     ('Take payment', 'take_payment')],
                      'text': ['Owner agrees', 'to pay later.']},
    'catch_cat': {   'choices': [('Back to desk', 'start')],
                     'text': ['Cat secured,', 'crisis over.']},
    'chaos': {   'choices': [   ('Fix it', 'fix_it'),
                                ('Back', 'start'),
                                ('Lost cat', 'lost_cat')],
                 'text': ['Destiny misplaces', 'paperwork again.']},
    'check_anesthesia': {   'choices': [   ('Refill', 'refill_iso'),
                                           ('Alert vet', 'alert_vet'),
                                           ('Back', 'start')],
                            'text': ['Isoflurane low', 'on machine.']},
    'check_fridge': {   'choices': [   ('Toss leftovers', 'toss_leftovers'),
                                       ('Back', 'break_room')],
                        'text': ['Fridge crowded', 'with old food.']},
    'check_meds': {   'choices': [('Back to desk', 'start')],
                      'text': ['Pills counted', 'and logged.']},
    'check_weight': {   'choices': [   ('Note record', 'note_weight'),
                                       ('Return', 'start')],
                        'text': ['Patient heavier', 'than last visit.']},
    'collect_deposit': {   'choices': [('Back to desk', 'start')],
                           'text': ['Deposit secured', 'for visit.']},
    'confirm_apps': {   'choices': [   ('Mark updated', 'wrap_up'),
                                       ('Send texts', 'send_texts'),
                                       (   'Note cancellations',
                                           'note_cancellation')],
                        'text': ['Clients confirm or', 'reschedule.']},
    'doyle': {   'choices': [   ('Back to desk', 'wrap_up'),
                                ('Walk-in', 'walk_in')],
                 'text': ['Dr. Doyle thanks', 'you for the info.']},
    'emergency_call': {   'choices': [   ('Prep room', 'prep_er_room'),
                                         ('Call vet', 'call_vet'),
                                         ('Back', 'start')],
                          'text': ['Hit-by-car dog', 'arriving soon.']},
    'end': {'choices': [], 'text': ['5pm hits.', 'Time to go home!']},
    'er_arrives': {   'choices': [   ('Assist vet', 'assist_surgery'),
                                     ('Grab fluids', 'grab_fluids')],
                      'text': ['Critical dog', 'arrives now!']},
    'exam_ready': {   'choices': [   ('Relay to vet', 'relay_vet'),
                                     ('Get vitals', 'vitals'),
                                     ('Back', 'start')],
                      'text': ['Maddie signals', 'a patient ready.']},
    'find_nova': {   'choices': [('Assist', 'assist_nova'), ('Back', 'start')],
                     'text': ['Nova needs help', 'calling a client.']},
    'firm': {   'choices': [   ('Back to desk', 'start'),
                               ('Answer phone', 'phone_rings'),
                               ('Ask Abby file', 'abby_file')],
                'text': ['Abby sighs and', 'backs away.']},
    'fix_it': {   'choices': [('Back to desk', 'start')],
                  'text': ['You fix the mess', 'without fuss.']},
    'flag_urgent': {   'choices': [('Back to desk', 'start')],
                       'text': ['Urgent flag', 'added to note.']},
    'front_desk': {   'choices': [   ('Stay firm', 'firm'),
                                     ('Let her', 'chaos'),
                                     ('Back', 'start')],
                      'text': ['Abby steps in,', 'adding confusion.']},
    'grab_fluids': {   'choices': [('Back to desk', 'start')],
                       'text': ['Fluids ready', 'for vet.']},
    'grab_net': {   'choices': [('Return to desk', 'start')],
                    'text': ['You snag the', 'cat quickly.']},
    'help_abby': {   'choices': [('Back to desk', 'start')],
                     'text': ['Together you', 'finish quickly.']},
    'help_paul': {   'choices': [('Wait for vet', 'wait_vet')],
                     'text': ['Room prepped', 'efficiently.']},
    'lab_call_owner': {   'choices': [   ('Back to desk', 'start'),
                                         (   'Schedule recheck',
                                             'schedule_recheck')],
                          'text': ['Owner thanks you', 'for the update.']},
    'lab_notify_vet': {   'choices': [   ('Back to desk', 'start'),
                                         ('Update record', 'update_record')],
                          'text': ['Anderson notes', 'the results.']},
    'lab_results': {   'choices': [   ('Call owner', 'lab_call_owner'),
                                      ('Notify vet', 'lab_notify_vet'),
                                      ('Back', 'start')],
                       'text': ["Fluffy's labs", 'are completed.']},
    'log_shortage': {   'choices': [('Back to desk', 'start')],
                        'text': ['Shortage noted', 'for reorder.']},
    'lost_cat': {   'choices': [   ('Calm clients', 'calm_clients'),
                                   ('Grab net', 'grab_net'),
                                   ('Back', 'start')],
                    'text': ['A cat escapes', 'into lobby!']},
    'messages': {   'choices': [   ('Tell Anderson', 'anderson'),
                                   ('Call client', 'call_client'),
                                   ('Check techs', 'tech_room')],
                    'text': ['Clients left', 'several messages.']},
    'note_cancellation': {   'choices': [('Back', 'schedule')],
                             'text': ['Canceled spots', 'reopened.']},
    'note_weight': {   'choices': [('Back to desk', 'start')],
                       'text': ['Record updated', 'for vet.']},
    'offer_help': {   'choices': [   ('Return to desk', 'start'),
                                     ('Check anesthesia', 'check_anesthesia'),
                                     ('Suture packs', 'suture_packs')],
                      'text': ['Paul and Pablo', 'grab supplies.']},
    'open_slot': {   'choices': [   ('Tell Doyle', 'doyle'),
                                    ('Leave open', 'wrap_up'),
                                    ('Back', 'schedule')],
                     'text': ['3pm slot is', 'available today.']},
    'oxygen_check': {   'choices': [   ('Replace tank', 'replace_tank'),
                                       ('Back', 'prep_er_room')],
                        'text': ['Oxygen tank', 'running low.']},
    'pharmacy_stock': {   'choices': [   ('Log shortage', 'log_shortage'),
                                         ('Back', 'start')],
                          'text': ['Shelves show some', 'drugs running low.']},
    'phone_rings': {   'choices': [   ('Calm them', 'calm_owner'),
                                      ('Transfer vet', 'transfer_vet'),
                                      ('Back', 'start')],
                       'text': ['Caller upset', 'about a bill.']},
    'prep_er_room': {   'choices': [   ('Help him', 'help_paul'),
                                       ('Call vet', 'call_vet'),
                                       ('Check oxygen', 'oxygen_check')],
                        'text': ['You and Paul', 'ready supplies.']},
    'record_note': {   'choices': [   ('Wrap up', 'wrap_up'),
                                      ('Flag urgent', 'flag_urgent')],
                       'text': ['Note saved for', 'the vets.']},
    'refill_iso': {   'choices': [('Back to desk', 'start')],
                      'text': ['Tank replaced', 'successfully.']},
    'relay_vet': {   'choices': [   ('Back to desk', 'start'),
                                    ('Take ER call', 'emergency_call')],
                     'text': ['You alert Dr.', 'Anderson.']},
    'replace_tank': {   'choices': [('Back', 'prep_er_room')],
                        'text': ['New tank in', 'place quickly.']},
    'schedule': {   'choices': [   ('Confirm clients', 'confirm_apps'),
                                   ('Find open slot', 'open_slot'),
                                   ('Exam room', 'exam_ready')],
                    'text': ['You review the', 'appointment list.']},
    'schedule_lunch': {   'choices': [('Back to desk', 'start')],
                          'text': ['Lunch planned', 'for Friday.']},
    'schedule_recheck': {   'choices': [('Back to desk', 'start')],
                            'text': ['Recheck set for', 'next week.']},
    'send_texts': {   'choices': [('Back', 'schedule')],
                      'text': ['Reminder texts', 'sent to all.']},
    'share_idea': {   'choices': [('Back to desk', 'start')],
                      'text': ['Team loves your', 'suggestion.']},
    'staff_meeting': {   'choices': [   ('Take notes', 'take_notes'),
                                        ('Share idea', 'share_idea'),
                                        ('Back', 'start')],
                         'text': ['Quick meeting', 'about tomorrow.']},
    'start': {   'choices': [   ('Check messages', 'messages'),
                                ('Look at schedule', 'schedule'),
                                ('Front desk', 'front_desk')],
                 'text': ['Gorgina begins', 'her day at desk.']},
    'supply_orders': {   'choices': [   ('Check pharmacy', 'pharmacy_stock'),
                                        ('Back', 'start')],
                         'text': ['She reviews low', 'inventory items.']},
    'suture_packs': {   'choices': [('Back to desk', 'start')],
                        'text': ['Suture packs', 'restocked.']},
    'take_notes': {   'choices': [('Back to desk', 'start')],
                      'text': ['Notes recorded', 'for the team.']},
    'take_payment': {   'choices': [('Back to desk', 'start')],
                        'text': ['Payment taken', 'over phone.']},
    'tech_room': {   'choices': [   ('Offer help', 'offer_help'),
                                    ('Back', 'start'),
                                    ('Lab results', 'lab_results')],
                     'text': ['Mel and Maddie', 'prep for surgery.']},
    'text_update': {   'choices': [('Wait', 'wait_vet')],
                       'text': ['Vet replies', 'almost instantly.']},
    'toss_leftovers': {   'choices': [('Back to desk', 'start')],
                          'text': ['Fridge cleaned', 'and organized.']},
    'training_chat': {   'choices': [   ('Set meeting', 'training_set'),
                                        ('Back to desk', 'start')],
                         'text': ['Nova wants more', 'phone tips soon.']},
    'training_set': {   'choices': [('Back to desk', 'start')],
                        'text': ['Training set for', 'next Tuesday.']},
    'transfer_vet': {   'choices': [('Back to desk', 'start')],
                        'text': ['Vet takes over', 'the call.']},
    'update_record': {   'choices': [('Back to desk', 'start')],
                         'text': ['Record updated', 'with new labs.']},
    'vitals': {   'choices': [   ('Back to desk', 'start'),
                                 ('Check weight', 'check_weight')],
                  'text': ['Paul records the', 'vitals with you.']},
    'wait_vet': {   'choices': [   ('Return to desk', 'start'),
                                   ('Dog arrives', 'er_arrives')],
                    'text': ['Patient stable', 'for now.']},
    'walk_in': {   'choices': [   ('Back to desk', 'start'),
                                  ('Collect deposit', 'collect_deposit')],
                   'text': ['A walk-in', 'added to slot.']},
    'wrap_up': {   'choices': [   ('Clock out', 'end'),
                                  ('Check desk', 'start'),
                                  ('Grab snack', 'break_room')],
                   'text': ["It's nearly 5pm.", 'Anything else?']}}


def init(display_func, fonts_tuple, quit_callback):
    global thread_safe_display, fonts, exit_cb
    thread_safe_display = display_func
    fonts = fonts_tuple
    exit_cb = quit_callback


def start():
    global state
    state = "start"
    draw()


def handle_input(pin):
    global state
    if state == "end":
        exit_cb()
        return
    step = STEPS[state]
    if pin == "KEY1" and len(step["choices"]) >= 1:
        state = step["choices"][0][1]
    elif pin == "KEY2" and len(step["choices"]) >= 2:
        state = step["choices"][1][1]
    elif pin == "KEY3" and len(step["choices"]) >= 3:
        state = step["choices"][2][1]
    elif pin == "JOY_PRESS":
        exit_cb()
        return
    draw()


def draw():
    step = STEPS[state]
    img = Image.new("RGB", (128, 128), "black")
    d = ImageDraw.Draw(img)
    d.text((5, 5), step["text"][0], font=fonts[1], fill=(255, 255, 255))
    d.text((5, 25), step["text"][1], font=fonts[1], fill=(255, 255, 255))
    if step["choices"]:
        y = 70
        for idx, (label, _) in enumerate(step["choices"], 1):
            d.text((5, y), f"{idx}={label}", font=fonts[0], fill=(0, 255, 255))
            y += 12
    else:
        d.text((25, 70), "(Press)", font=fonts[0], fill=(0, 255, 255))
    thread_safe_display(img)
    if state == "end":
        time.sleep(2)
        exit_cb()
