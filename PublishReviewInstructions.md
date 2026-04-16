Pipeline (end-to-end on each new doc):                    
  1. Auth via service account (n8n/noted-sled-489022-a2-2d59b1c03f2f.json) — no 
  browser flow needed                                                           
  2. List Google Docs in the configured folder, filter out already-processed    
  ones                                                                          
  3. Export each doc as HTML via Drive API                                      
  4. Parse the metadata table (first table in the doc) → all {{PLACEHOLDER}}
  values                                                                        
  5. Split body at H2 section headings → five required sections + optional      
  References                                                                    
  6. Clean Google's exported HTML: strips style/id/class, unwraps <span>s, fixes
   redirect URLs                                                                
  7. Process [CALLOUT] and [QUOTE] markers → site-styled callout/blockquote     
  boxes                                                                    
  8. Fill Reviews/_review-template.html with rendered content                   
  9. Write Reviews/{slug}.html                               
  10. Inject a card into papers-of-note.html (newest first, duplicate-safe)     
  11. Record doc ID in .review_state.json                                       
                                                                                
  To use it:                                                                    
  1. Set REVIEW_FOLDER_ID at the top of the script (from the Drive folder URL)  
  2. Share the Drive folder with the service account email in the JSON key      
  3. uv run publish_review.py — processes everything new                  
  4. uv run publish_review.py --doc-id ID --dry-run — safe preview before       
  committing  