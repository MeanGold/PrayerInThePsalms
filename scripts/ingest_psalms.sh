#!/bin/bash
# Script to run data ingestion for initial psalm dataset
# Requirements: 5.4, 6.1

set -e

echo "=========================================="
echo "Psalm Data Ingestion"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running from project root
if [ ! -f "app.py" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

# Check for required tools
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI not found. Please install AWS CLI.${NC}"
    exit 1
fi

# Get region
REGION=$(aws configure get region || echo "us-east-1")

# Get Lambda function name from stack outputs
echo -e "${YELLOW}Retrieving Lambda function name...${NC}"
if [ -f "deployment-outputs.json" ]; then
    LAMBDA_ARN=$(jq -r '.[] | select(.OutputKey=="IngestionLambdaArn") | .OutputValue' deployment-outputs.json)
    LAMBDA_NAME=$(echo "$LAMBDA_ARN" | awk -F: '{print $NF}')
else
    # Fallback to default name
    LAMBDA_NAME="psalm-data-ingestion"
fi

echo -e "${GREEN}  ✓ Lambda function: ${LAMBDA_NAME}${NC}"

# Check if Lambda function exists
if ! aws lambda get-function --function-name "$LAMBDA_NAME" --region "$REGION" &> /dev/null; then
    echo -e "${RED}Error: Lambda function '${LAMBDA_NAME}' not found${NC}"
    echo "Make sure you have deployed the stack first: ./scripts/deploy_stack.sh"
    exit 1
fi

# Check for psalm data file
PSALM_DATA_FILE="${1:-data/psalms.json}"

if [ ! -f "$PSALM_DATA_FILE" ]; then
    echo -e "${YELLOW}Psalm data file not found: ${PSALM_DATA_FILE}${NC}"
    echo ""
    echo "Creating sample psalm data file..."
    
    # Create data directory if it doesn't exist
    mkdir -p data
    
    # Create sample psalm data
    cat > "$PSALM_DATA_FILE" << 'EOF'
{
  "psalms": [
    {
      "number": 23,
      "text": "The Lord is my shepherd, I lack nothing. He makes me lie down in green pastures, he leads me beside quiet waters, he refreshes my soul. He guides me along the right paths for his name's sake. Even though I walk through the darkest valley, I will fear no evil, for you are with me; your rod and your staff, they comfort me. You prepare a table before me in the presence of my enemies. You anoint my head with oil; my cup overflows. Surely your goodness and love will follow me all the days of my life, and I will dwell in the house of the Lord forever.",
      "themes": ["comfort", "trust", "guidance", "protection", "provision"],
      "emotional_context": "anxiety, fear, uncertainty, need for comfort, seeking peace",
      "historical_usage": "Used in times of distress and uncertainty, funerals, pastoral care",
      "key_verses": ["verse 1: The Lord is my shepherd", "verse 4: Even though I walk through the darkest valley, I will fear no evil"]
    },
    {
      "number": 46,
      "text": "God is our refuge and strength, an ever-present help in trouble. Therefore we will not fear, though the earth give way and the mountains fall into the heart of the sea, though its waters roar and foam and the mountains quake with their surging. There is a river whose streams make glad the city of God, the holy place where the Most High dwells. God is within her, she will not fall; God will help her at break of day. Nations are in uproar, kingdoms fall; he lifts his voice, the earth melts. The Lord Almighty is with us; the God of Jacob is our fortress. Come and see what the Lord has done, the desolations he has brought on the earth. He makes wars cease to the ends of the earth. He breaks the bow and shatters the spear; he burns the shields with fire. He says, 'Be still, and know that I am God; I will be exalted among the nations, I will be exalted in the earth.' The Lord Almighty is with us; the God of Jacob is our fortress.",
      "themes": ["refuge", "strength", "peace", "trust", "God's presence"],
      "emotional_context": "fear, chaos, turmoil, need for stability, seeking calm",
      "historical_usage": "Times of national crisis, natural disasters, personal upheaval",
      "key_verses": ["verse 1: God is our refuge and strength", "verse 10: Be still, and know that I am God"]
    },
    {
      "number": 139,
      "text": "You have searched me, Lord, and you know me. You know when I sit and when I rise; you perceive my thoughts from afar. You discern my going out and my lying down; you are familiar with all my ways. Before a word is on my tongue you, Lord, know it completely. You hem me in behind and before, and you lay your hand upon me. Such knowledge is too wonderful for me, too lofty for me to attain. Where can I go from your Spirit? Where can I flee from your presence? If I go up to the heavens, you are there; if I make my bed in the depths, you are there. If I rise on the wings of the dawn, if I settle on the far side of the sea, even there your hand will guide me, your right hand will hold me fast. Search me, God, and know my heart; test me and know my anxious thoughts. See if there is any offensive way in me, and lead me in the way everlasting.",
      "themes": ["God's omniscience", "God's presence", "self-examination", "guidance", "intimacy with God"],
      "emotional_context": "feeling lost, seeking identity, need for understanding, desire for closeness with God",
      "historical_usage": "Personal reflection, spiritual direction, times of self-doubt",
      "key_verses": ["verse 1: You have searched me, Lord, and you know me", "verse 23-24: Search me, God, and know my heart"]
    },
    {
      "number": 91,
      "text": "Whoever dwells in the shelter of the Most High will rest in the shadow of the Almighty. I will say of the Lord, 'He is my refuge and my fortress, my God, in whom I trust.' Surely he will save you from the fowler's snare and from the deadly pestilence. He will cover you with his feathers, and under his wings you will find refuge; his faithfulness will be your shield and rampart. You will not fear the terror of night, nor the arrow that flies by day, nor the pestilence that stalks in the darkness, nor the plague that destroys at midday. A thousand may fall at your side, ten thousand at your right hand, but it will not come near you. If you say, 'The Lord is my refuge,' and you make the Most High your dwelling, no harm will overtake you, no disaster will come near your tent. For he will command his angels concerning you to guard you in all your ways.",
      "themes": ["protection", "trust", "safety", "God's faithfulness", "deliverance"],
      "emotional_context": "fear, danger, vulnerability, need for protection, seeking safety",
      "historical_usage": "Times of illness, danger, warfare, protection prayers",
      "key_verses": ["verse 1-2: Whoever dwells in the shelter of the Most High", "verse 11: He will command his angels concerning you"]
    },
    {
      "number": 42,
      "text": "As the deer pants for streams of water, so my soul pants for you, my God. My soul thirsts for God, for the living God. When can I go and meet with God? My tears have been my food day and night, while people say to me all day long, 'Where is your God?' These things I remember as I pour out my soul: how I used to go to the house of God under the protection of the Mighty One with shouts of joy and praise among the festive throng. Why, my soul, are you downcast? Why so disturbed within me? Put your hope in God, for I will yet praise him, my Savior and my God.",
      "themes": ["longing for God", "depression", "hope", "spiritual thirst", "perseverance"],
      "emotional_context": "sadness, depression, spiritual dryness, longing, discouragement",
      "historical_usage": "Times of spiritual dryness, depression, feeling distant from God",
      "key_verses": ["verse 1: As the deer pants for streams of water", "verse 11: Why, my soul, are you downcast? Put your hope in God"]
    }
  ]
}
EOF
    
    echo -e "${GREEN}  ✓ Sample psalm data created: ${PSALM_DATA_FILE}${NC}"
fi

# Display psalm data summary
PSALM_COUNT=$(jq '.psalms | length' "$PSALM_DATA_FILE")
echo -e "\n${BLUE}Psalm Data Summary:${NC}"
echo "  File: ${PSALM_DATA_FILE}"
echo "  Psalms to ingest: ${PSALM_COUNT}"

# Confirm ingestion
echo ""
read -p "Proceed with ingestion? (y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Ingestion cancelled${NC}"
    exit 0
fi

# Invoke Lambda function
echo -e "\n${YELLOW}Invoking data ingestion Lambda...${NC}"
echo "This may take a few minutes depending on the number of psalms."

# Create temporary response file
RESPONSE_FILE=$(mktemp)

# Invoke Lambda with payload
aws lambda invoke \
    --function-name "$LAMBDA_NAME" \
    --region "$REGION" \
    --payload "file://${PSALM_DATA_FILE}" \
    --cli-binary-format raw-in-base64-out \
    "$RESPONSE_FILE"

# Check response
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}Lambda invocation successful${NC}"
    
    # Display response
    echo -e "\n${YELLOW}Response:${NC}"
    cat "$RESPONSE_FILE" | jq '.'
    
    # Check for errors in response
    if jq -e '.errorMessage' "$RESPONSE_FILE" > /dev/null 2>&1; then
        echo -e "\n${RED}Error during ingestion:${NC}"
        jq -r '.errorMessage' "$RESPONSE_FILE"
        rm "$RESPONSE_FILE"
        exit 1
    fi
    
    # Display success summary
    INGESTED_COUNT=$(jq -r '.body | fromjson | .ingested_count // 0' "$RESPONSE_FILE" 2>/dev/null || echo "0")
    
    echo -e "\n${GREEN}=========================================="
    echo "Ingestion complete!"
    echo "==========================================${NC}"
    echo "  Psalms ingested: ${INGESTED_COUNT}"
    
    echo -e "\n${YELLOW}Next steps:${NC}"
    echo "  1. Wait 1-2 minutes for embeddings to be indexed"
    echo "  2. Test the recommendation API:"
    echo ""
    
    if [ -f "deployment-outputs.json" ]; then
        API_ENDPOINT=$(jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue' deployment-outputs.json)
        echo "     curl -X POST ${API_ENDPOINT}recommend \\"
        echo "       -H 'Content-Type: application/json' \\"
        echo "       -d '{\"emotional_input\": \"I am feeling anxious and worried.\"}'"
    else
        echo "     curl -X POST https://YOUR_API_ENDPOINT/prod/recommend \\"
        echo "       -H 'Content-Type: application/json' \\"
        echo "       -d '{\"emotional_input\": \"I am feeling anxious and worried.\"}'"
    fi
    
else
    echo -e "\n${RED}Lambda invocation failed${NC}"
    cat "$RESPONSE_FILE"
    rm "$RESPONSE_FILE"
    exit 1
fi

# Cleanup
rm "$RESPONSE_FILE"
