#include <SoftwareSerial.h>
#include <EEPROM.h>

// ==========================================
//               CONFIGURATION
// ==========================================
// !!! CHANGE THIS FOR EACH MODULE TODAY !!!
// On the very first boot, the firmware will save this to EEPROM.
// On all future boots/reflashes, this variable is ignored.
const uint8_t HARDCODED_ID = 44; 

const String FLAP_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$&()-+=;q:%'.,/?*roygbpw";

// EEPROM MAP
const int ADDR_INIT = 0;          // 1 byte  - Initialization flag
const int ADDR_HOME_OFFSET = 1;   // 2 bytes - Offset from magnet
const int ADDR_TOTAL_STEPS = 3;   // 2 bytes - Step length of reel
const int ADDR_MODULE_ID = 5;     // 1 byte  - The Module's Assigned ID (0-44)
const int ADDR_MAP_START = 10;    // 128 bytes - Exact character positions
const uint8_t INIT_VALUE = 0x5C;  // Magic number (Changed to 5C for this new logic)

// Operating Variables
uint8_t moduleId = 255;
char idChars[2] = {'*', '*'};

int stepsFromHallToZero = 2832;
int totalStepsPerRev = 4096;

// ==========================================
//              PIN DEFINITIONS
// ==========================================
const int RS485_RX = 3;
const int RS485_TX = 1;
const int RS485_DE = 2;

#define IN1 9
#define IN2 8
#define IN3 7
#define IN4 6
#define HALL_PIN 4

// ==========================================
//               GLOBALS
// ==========================================
SoftwareSerial rs485(RS485_RX, RS485_TX);

long currentStepPos = 0; 
int currentPhase = 0;
int parseState = 0; 
int currentFlapIndex = -1;
int tempIndex = -1;

const int stepDelay = 1;
String buffer = "";
unsigned long lastSerialTime = 0;

const uint8_t halfStepSequence[8][4] = {
  {1, 0, 0, 0}, {1, 1, 0, 0}, {0, 1, 0, 0}, {0, 1, 1, 0},
  {0, 0, 1, 0}, {0, 0, 1, 1}, {0, 0, 0, 1}, {1, 0, 0, 1}
};

// ==========================================
//             EEPROM FUNCTIONS
// ==========================================

void saveHomeOffset() { EEPROM.put(ADDR_HOME_OFFSET, stepsFromHallToZero); }
void saveTotalSteps() { EEPROM.put(ADDR_TOTAL_STEPS, totalStepsPerRev); }

void updateIdChars() {
  if(moduleId < 100) {
    idChars[0] = (moduleId / 10) + '0';
    idChars[1] = (moduleId % 10) + '0';
  }
}

// ==========================================
//             MOTOR FUNCTIONS
// ==========================================

void applyStep(const uint8_t *step) {
  digitalWrite(IN1, step[0]);
  digitalWrite(IN2, step[1]);
  digitalWrite(IN3, step[2]); 
  digitalWrite(IN4, step[3]);
}

void stepBackward(int steps) {
  for (int k = 0; k < steps; k++) {
    bool hallNow = hallActive();
    static bool lastHallState = false;

    if (hallNow && !lastHallState) {
      currentStepPos = totalStepsPerRev - stepsFromHallToZero;
    }
    lastHallState = hallNow;

    currentPhase--;
    if (currentPhase < 0) {
      currentPhase = 7;
    }
    
    applyStep(halfStepSequence[currentPhase]);
    delay(stepDelay);
    
    currentStepPos++;
    if (currentStepPos >= totalStepsPerRev) {
      currentStepPos = 0;
    }
  }
}

void releaseMotor() {
  digitalWrite(IN1,0); digitalWrite(IN2,0); digitalWrite(IN3,0); digitalWrite(IN4,0);
}

bool hallActive() {
  return (digitalRead(HALL_PIN) == LOW);
}

// ==========================================
//             LOGIC FUNCTIONS
// ==========================================

void homeModule() {
  long safety = 0;
  while (!hallActive() && safety < (totalStepsPerRev + 500)) {
    stepBackward(1);
    safety++;
  }
  
  stepBackward(stepsFromHallToZero);
  currentStepPos = 0; 
  currentFlapIndex = 0;
  releaseMotor();
}

void calibrateModule() {
  long safety = 0;
  while (hallActive() && safety < 4000) {
    stepBackward(1);
    safety++;
    delay(5);
  }

  safety = 0;
  while (!hallActive() && safety < 5000) {
    stepBackward(1);
    safety++;
  }

  while (hallActive()) {
    stepBackward(1);
  }

  int measuredSteps = 0;
  while (!hallActive() && measuredSteps < 5000) {
    stepBackward(1);
    measuredSteps++;
  }

  while (hallActive()) {
    stepBackward(1);
    measuredSteps++;
  }

  digitalWrite(RS485_DE, HIGH);
  delay(5); 
  
  rs485.print("m");
  if(moduleId < 100) {
    rs485.print(idChars[0]);
    rs485.print(idChars[1]);
  } else {
    rs485.print("XX");
  }
  rs485.print(":");
  rs485.println(measuredSteps);
  
  rs485.flush(); 
  delay(5);
  digitalWrite(RS485_DE, LOW);
  
  totalStepsPerRev = measuredSteps;
  saveTotalSteps();
  homeModule();
}

void moveToChar(char targetChar) {
  int targetIndex = FLAP_CHARS.indexOf(targetChar);
  if (targetIndex == -1) return;
  if (currentFlapIndex == targetIndex) return; 
  
  if (currentFlapIndex == -1) {
    homeModule();
  }

  uint16_t mappedPos = 0xFFFF;
  EEPROM.get(ADDR_MAP_START + (targetIndex * 2), mappedPos);
  
  long targetStepPos;
  if (mappedPos != 0xFFFF) {
    targetStepPos = mappedPos;
  } else {
    targetStepPos = ((long)targetIndex * (long)totalStepsPerRev) / 64;
  }
  
  long stepsToMove = targetStepPos - currentStepPos;
  if (stepsToMove < 0) {
    stepsToMove += totalStepsPerRev;
  }
  
  while(stepsToMove > 0) {
    stepBackward(1);
    stepsToMove--;
  }

  releaseMotor();
  currentFlapIndex = targetIndex; 
}

// ==========================================
//              MAIN LOOP
// ==========================================

void setup() {
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); 
  pinMode(IN4, OUTPUT);
  pinMode(HALL_PIN, INPUT_PULLUP);
  
  pinMode(RS485_DE, OUTPUT);
  digitalWrite(RS485_DE, LOW); 
  
  // --- THE BOOTSTRAP LOGIC ---
  if (EEPROM.read(ADDR_INIT) == INIT_VALUE) {
    // THIS IS A FUTURE BOOT
    // Ignore HARDCODED_ID entirely and load from memory
    EEPROM.get(ADDR_HOME_OFFSET, stepsFromHallToZero);
    EEPROM.get(ADDR_TOTAL_STEPS, totalStepsPerRev);
    moduleId = EEPROM.read(ADDR_MODULE_ID);
  } else {
    // THIS IS THE VERY FIRST BOOT
    // Format EEPROM and burn the HARDCODED_ID permanently
    EEPROM.write(ADDR_INIT, INIT_VALUE);
    saveHomeOffset();
    saveTotalSteps();
    
    moduleId = HARDCODED_ID; 
    EEPROM.write(ADDR_MODULE_ID, moduleId);
    
    // Wipe character map clean
    for(int i=0; i<64; i++) {
      uint16_t empty = 0xFFFF;
      EEPROM.put(ADDR_MAP_START + (i*2), empty);
    }
  }

  updateIdChars();

  rs485.begin(9600);

  if (moduleId != 255) {
    delay(moduleId * 150); 
  }
  
  homeModule();
}

void loop() {
  while (rs485.available()) {
    char c = rs485.read();
    lastSerialTime = millis();
    
    switch (parseState) {
      case 0: if (c == 'm') parseState = 1; break;
      case 1: if (c == idChars[0] || c == '*') parseState = 2; else parseState = 0; break;
      case 2: if (c == idChars[1] || c == '*') parseState = 3; else parseState = 0; break;
      
      case 3: 
        if (c == '-') parseState = 4;
        else if (c == 'h') { homeModule(); parseState = 0; }
        else if (c == 'c') { calibrateModule(); parseState = 0; }
        else if (c == 'o') { buffer = ""; parseState = 5; }
        else if (c == 't') { buffer = ""; parseState = 6; }
        else if (c == 's') { buffer = ""; parseState = 7; } 
        else if (c == 'g') { buffer = ""; parseState = 8; } 
        else if (c == 'w') { buffer = ""; tempIndex = -1; parseState = 9; } 
        else if (c == 'i') { buffer = ""; parseState = 10; } 
        else if (c == 'e') { 
          for(int i=0; i<64; i++) {
            uint16_t empty = 0xFFFF;
            EEPROM.put(ADDR_MAP_START + (i*2), empty);
          }
          parseState = 0;
        } 
        else parseState = 0;
        break;
        
      case 4: moveToChar(c); parseState = 0; break;
      
      case 5: 
        if (isDigit(c)) buffer += c;
        else { 
          if (buffer.length()>0) {
            stepsFromHallToZero = buffer.toInt(); 
            saveHomeOffset();
          }
          parseState=0; 
        }
        break;
        
      case 6: 
        if (isDigit(c)) buffer += c;
        else { 
          if (buffer.length()>0) {
            totalStepsPerRev = buffer.toInt(); 
            saveTotalSteps();
          }
          parseState=0; 
        }
        break;
        
      case 7: 
        if (isDigit(c)) buffer += c;
        else { 
          if (buffer.length()>0) {
            int stepsToMove = buffer.toInt();
            stepBackward(stepsToMove);
            releaseMotor();
            stepsFromHallToZero += stepsToMove;
            saveHomeOffset();
          }
          parseState=0; 
        }
        break;
        
      case 8: 
        if (isDigit(c)) buffer += c;
        else {
          if (buffer.length() > 0) {
            long targetStep = buffer.toInt();
            long stepsToMove = targetStep - currentStepPos;
            if (stepsToMove < 0) stepsToMove += totalStepsPerRev;
            while(stepsToMove > 0) { stepBackward(1); stepsToMove--; }
            releaseMotor();
            currentFlapIndex = -2;
          }
          parseState = 0;
        }
        break;
        
      case 9: 
        if (c == ':') {
          tempIndex = buffer.toInt();
          buffer = "";
        } else if (isDigit(c)) {
          buffer += c;
        } else {
          if (buffer.length() > 0 && tempIndex != -1) {
            uint16_t pos = buffer.toInt();
            EEPROM.put(ADDR_MAP_START + (tempIndex * 2), pos);
          }
          parseState = 0;
        }
        break;

      case 10: // Manual ID Override via Serial
        if (isDigit(c)) buffer += c;
        else {
          if (buffer.length() > 0) {
            moduleId = buffer.toInt();
            EEPROM.write(ADDR_MODULE_ID, moduleId);
            updateIdChars();
          }
          parseState = 0;
        }
        break;
    }
  }

  // Timeouts for number parsing
  if ((parseState >= 5 && parseState <= 10) && (millis() - lastSerialTime > 50)) {
    if (buffer.length() > 0) {
      if (parseState == 5) { stepsFromHallToZero = buffer.toInt(); saveHomeOffset(); }
      if (parseState == 6) { totalStepsPerRev = buffer.toInt(); saveTotalSteps(); }
      if (parseState == 7) {
        int stepsToMove = buffer.toInt();
        stepBackward(stepsToMove);
        releaseMotor();
        stepsFromHallToZero += stepsToMove;
        saveHomeOffset();
      }
      if (parseState == 8) {
        long targetStep = buffer.toInt();
        long stepsToMove = targetStep - currentStepPos;
        if (stepsToMove < 0) stepsToMove += totalStepsPerRev;
        while(stepsToMove > 0) { stepBackward(1); stepsToMove--; }
        releaseMotor();
        currentFlapIndex = -2;
      }
      if (parseState == 9 && tempIndex != -1) {
        uint16_t pos = buffer.toInt();
        EEPROM.put(ADDR_MAP_START + (tempIndex * 2), pos);
      }
      if (parseState == 10) {
        moduleId = buffer.toInt();
        EEPROM.write(ADDR_MODULE_ID, moduleId);
        updateIdChars();
      }
    }
    parseState = 0;
  }
}